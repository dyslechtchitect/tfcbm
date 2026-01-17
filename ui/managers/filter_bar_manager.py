"""Manages the filter bar UI and filter state."""

import asyncio
import json
import logging
import threading
from typing import Callable, Set

import gi
from ui.services.ipc_helpers import connect as ipc_connect

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")

from gi.repository import Gdk, GLib, Gtk

logger = logging.getLogger("TFCBM.FilterBarManager")


class FilterBarManager:
    """Manages filter bar UI, content type filters, and filter state."""

    def __init__(self, on_filter_changed: Callable[[], None]):
        """Initialize FilterBarManager.

        Args:
            on_filter_changed: Callback when filters change (should reload items)
        """
        self.on_filter_changed = on_filter_changed

        # Filter state
        self.active_filters: Set[str] = set()
        self.file_extensions = []
        self.system_filters_visible = True

        # UI components
        self.filter_bar = None
        self.filter_box = None
        self.filter_scroll = None
        self.filter_toggle_btn = None
        self.filter_sort_btn = None
        self.system_filter_chips = []

        # Store signal handler IDs for each chip
        self.chip_signal_handlers = {}

        self._create_filter_bar()

    def build(self) -> Gtk.Box:
        """Return the filter bar widget.

        Returns:
            Gtk.Box: The filter bar container
        """
        return self.filter_bar

    def get_active_filters(self) -> Set[str]:
        """Get currently active filters.

        Returns:
            Set[str]: Set of active filter IDs
        """
        return self.active_filters.copy()

    def set_visible(self, visible: bool) -> None:
        """Show or hide the filter bar.

        Args:
            visible: True to show, False to hide
        """
        self.filter_bar.set_visible(visible)

    def clear_filters(self) -> None:
        """Clear all active filters programmatically."""
        self.active_filters.clear()
        for flow_child in list(self.filter_box):
            chip = flow_child.get_child()
            if isinstance(chip, Gtk.ToggleButton) and chip in self.chip_signal_handlers:
                # Block signal handler to prevent recursion
                handler_id = self.chip_signal_handlers[chip]
                chip.handler_block(handler_id)
                chip.set_active(False)
                chip.handler_unblock(handler_id)

    def _create_filter_bar(self):
        """Create the filter bar with system content types, file extensions, and controls."""
        # Main filter bar container
        self.filter_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.filter_bar.set_margin_top(6)
        self.filter_bar.set_margin_bottom(6)
        self.filter_bar.set_margin_start(8)
        self.filter_bar.set_margin_end(8)
        self.filter_bar.add_css_class("toolbar")
        self.filter_bar.set_visible(True)

        # Filter toggle button (to show/hide system filters) - currently unused
        self.filter_toggle_btn = Gtk.ToggleButton()
        icon_found = False
        for icon_name in [
            "funnel-symbolic",
            "filter-symbolic",
            "view-filter-symbolic",
            "preferences-system-symbolic",
        ]:
            theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
            if theme.has_icon(icon_name):
                self.filter_toggle_btn.set_icon_name(icon_name)
                logger.debug(f"Using icon: {icon_name}")
                icon_found = True
                break

        if not icon_found:
            self.filter_toggle_btn.set_label("⚙")
            logger.debug("No icon found, using text label fallback")

        self.filter_toggle_btn.set_tooltip_text("Show/hide system filters")
        self.filter_toggle_btn.add_css_class("flat")
        self.filter_toggle_btn.set_size_request(32, 32)
        self.filter_toggle_btn.set_visible(True)
        self.filter_toggle_btn.set_sensitive(True)

        # Scrollable container for filter chips
        self.filter_scroll = Gtk.ScrolledWindow()
        self.filter_scroll.set_policy(
            Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER
        )
        self.filter_scroll.set_hexpand(True)

        # FlowBox for filter chips (wraps automatically)
        self.filter_box = Gtk.FlowBox()
        self.filter_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self.filter_box.set_homogeneous(False)
        self.filter_box.set_column_spacing(4)
        self.filter_box.set_row_spacing(4)
        self.filter_box.set_max_children_per_line(20)

        self.filter_scroll.set_child(self.filter_box)
        self.filter_bar.append(self.filter_scroll)

        # Clear filters button (small x icon like tags)
        clear_btn = Gtk.Button()
        clear_btn.set_icon_name("window-close-symbolic")
        clear_btn.set_tooltip_text("Clear all filters")
        clear_btn.add_css_class("flat")
        clear_btn.set_size_request(24, 24)

        # Make it compact like the tag clear button
        css_provider = Gtk.CssProvider()
        css_data = "button { padding: 2px; min-height: 20px; min-width: 20px; }"
        css_provider.load_from_data(css_data.encode())
        clear_btn.get_style_context().add_provider(
            css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        clear_btn.connect("clicked", self._on_clear_filters)
        self.filter_bar.append(clear_btn)

        # Add system content type filters
        self._add_system_filters()

    def add_toolbar_separator(self) -> None:
        """Add a separator to the filter bar (called externally for layout control)."""
        separator = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        self.filter_bar.append(separator)

    def add_sort_button(
        self, on_sort_clicked: Callable[[], None], initial_tooltip: str = "Newest first ↓"
    ) -> Gtk.Button:
        """Add sort toggle button to the filter bar.

        Args:
            on_sort_clicked: Callback when sort button is clicked
            initial_tooltip: Initial tooltip text

        Returns:
            Gtk.Button: The created sort button
        """
        self.filter_sort_btn = Gtk.Button()
        self.filter_sort_btn.set_icon_name("view-sort-descending-symbolic")
        self.filter_sort_btn.set_tooltip_text(initial_tooltip)
        self.filter_sort_btn.add_css_class("flat")
        self.filter_sort_btn.add_css_class("sort-toggle")
        self.filter_sort_btn.connect("clicked", lambda btn: on_sort_clicked())
        self.filter_bar.append(self.filter_sort_btn)
        return self.filter_sort_btn

    def add_jump_to_top_button(
        self, on_jump_clicked: Callable[[], None]
    ) -> Gtk.Button:
        """Add jump to top button to the filter bar.

        Args:
            on_jump_clicked: Callback when jump button is clicked

        Returns:
            Gtk.Button: The created jump button
        """
        jump_btn = Gtk.Button()
        jump_btn.set_icon_name("go-top-symbolic")
        jump_btn.set_tooltip_text("Jump to top")
        jump_btn.add_css_class("flat")
        jump_btn.connect("clicked", lambda btn: on_jump_clicked())
        self.filter_bar.append(jump_btn)
        return jump_btn

    def _add_system_filters(self):
        """Add system content type filter buttons."""
        self.system_filter_chips = []
        system_filters = [
            ("favorite", "Favorites", "starred-symbolic"),
            ("text", "Text", "text-x-generic-symbolic"),
            ("image", "Images", "image-x-generic-symbolic"),
            ("url", "URLs", "web-browser-symbolic"),
            ("file", "Files", "folder-documents-symbolic"),
        ]

        for filter_type, label, icon_name in system_filters:
            chip = self._create_filter_chip(
                filter_type, label, icon_name, is_system=True
            )
            self.system_filter_chips.append(chip)

    def _create_filter_chip(
        self, filter_id: str, label: str, icon_name: str = None, is_system: bool = False
    ):
        """Create a small filter chip button.

        Args:
            filter_id: Unique identifier for this filter
            label: Display label for the chip
            icon_name: Optional icon name
            is_system: Whether this is a system filter

        Returns:
            Gtk.FlowBoxChild: The created filter chip
        """
        chip = Gtk.ToggleButton()
        chip.set_has_frame(False)
        chip.add_css_class("pill")

        chip_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)

        if icon_name:
            icon = Gtk.Image.new_from_icon_name(icon_name)
            icon.set_pixel_size(12)
            chip_box.append(icon)

        chip_label = Gtk.Label(label=label)
        chip_label.add_css_class("caption")
        chip_box.append(chip_label)

        chip.set_child(chip_box)

        # Apply compact styling for system filters (similar to tags)
        if is_system:
            css_provider = Gtk.CssProvider()
            css_data = "button.pill { padding: 2px 7px; min-height: 20px; }"
            css_provider.load_from_data(css_data.encode())
            chip.get_style_context().add_provider(
                css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

        # Connect toggle signal
        handler_id = chip.connect("toggled", lambda btn: self._on_filter_toggled(filter_id, btn))

        # Store the signal handler ID so we can block/unblock it later
        self.chip_signal_handlers[chip] = handler_id

        # Wrap in FlowBoxChild
        flow_child = Gtk.FlowBoxChild()
        flow_child.set_child(chip)

        # Show system filters by default
        if is_system:
            flow_child.set_visible(True)

        self.filter_box.append(flow_child)

        return flow_child

    def load_file_extensions(self):
        """Load available file extensions from server (currently disabled)."""

        async def fetch_extensions():
            try:
                async with ipc_connect() as conn:
                    request = {"action": "get_file_extensions"}
                    await conn.send(json.dumps(request))

                    response = await conn.recv()
                    data = json.loads(response)

                    if data.get("type") == "file_extensions":
                        extensions = data.get("extensions", [])

                        def update_ui():
                            self.file_extensions = extensions
                            for ext in extensions:
                                # Remove leading dot for display
                                display_ext = ext.lstrip(".")
                                # Get icon for this file type
                                icon_name = self._get_icon_for_extension(ext)
                                self._create_filter_chip(
                                    f"file:{ext}",
                                    display_ext.upper(),
                                    icon_name,
                                )
                            return False

                        GLib.idle_add(update_ui)

            except Exception as e:
                logger.error(f"Error loading file extensions: {e}")

        def run_async():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(fetch_extensions())
            finally:
                loop.close()

        threading.Thread(target=run_async, daemon=True).start()

    def _get_icon_for_extension(self, extension: str) -> str:
        """Get appropriate icon for file extension.

        Args:
            extension: File extension (with or without leading dot)

        Returns:
            str: Icon name
        """
        icon_map = {
            ".zip": "package-x-generic-symbolic",
            ".gz": "package-x-generic-symbolic",
            ".tar": "package-x-generic-symbolic",
            ".sh": "text-x-script-symbolic",
            ".py": "text-x-python-symbolic",
            ".txt": "text-x-generic-symbolic",
            ".pdf": "x-office-document-symbolic",
            ".doc": "x-office-document-symbolic",
            ".docx": "x-office-document-symbolic",
        }
        return icon_map.get(extension, "text-x-generic-symbolic")

    def _on_filter_toggled(self, filter_id: str, button: Gtk.ToggleButton):
        """Handle filter chip toggle.

        Args:
            filter_id: The filter ID that was toggled
            button: The toggle button that was clicked
        """
        if button.get_active():
            self.active_filters.add(filter_id)
        else:
            self.active_filters.discard(filter_id)

        logger.info(
            f"Toggled filter '{filter_id}', active: {button.get_active()}"
        )
        logger.info(f"Current active filters: {self.active_filters}")

        # Notify caller that filters changed
        self.on_filter_changed()

    def _on_clear_filters(self, button: Gtk.Button):
        """Clear all active filters.

        Args:
            button: The clear button that was clicked
        """
        self.active_filters.clear()

        # Uncheck all filter chips
        for flow_child in list(self.filter_box):
            chip = flow_child.get_child()
            if isinstance(chip, Gtk.ToggleButton) and chip in self.chip_signal_handlers:
                # Block signal handler to prevent recursion
                handler_id = self.chip_signal_handlers[chip]
                chip.handler_block(handler_id)
                chip.set_active(False)
                chip.handler_unblock(handler_id)

        # Notify caller that filters changed
        self.on_filter_changed()
