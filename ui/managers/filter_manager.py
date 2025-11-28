"""Filter management for clipboard items."""

from typing import Callable, Set

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk


class FilterManager:
    """Manages content type filters (text, file, image, url)."""

    def __init__(self, on_filter_change: Callable[[], None]):
        self.on_filter_change = on_filter_change
        self.active_filters: Set[str] = set()
        self.system_filters_visible = True
        self.filter_box = None
        self.filter_scroll = None
        self.filter_bar = None
        self.filter_toggle_btn = None
        self.filter_sort_btn = None
        self.system_filter_chips = []

    def build(self) -> Gtk.Widget:
        """Build the filter bar widget."""
        self.filter_bar = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=6
        )
        self.filter_bar.set_margin_top(6)
        self.filter_bar.set_margin_bottom(6)
        self.filter_bar.set_margin_start(8)
        self.filter_bar.set_margin_end(8)
        self.filter_bar.add_css_class("toolbar")
        self.filter_bar.set_visible(True)

        self.filter_scroll = Gtk.ScrolledWindow()
        self.filter_scroll.set_policy(
            Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER
        )
        self.filter_scroll.set_hexpand(True)

        self.filter_box = Gtk.FlowBox()
        self.filter_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self.filter_box.set_homogeneous(False)
        self.filter_box.set_column_spacing(4)
        self.filter_box.set_row_spacing(4)
        self.filter_box.set_max_children_per_line(20)

        self.filter_scroll.set_child(self.filter_box)
        self.filter_bar.append(self.filter_scroll)

        clear_btn = Gtk.Button()
        clear_btn.set_icon_name("edit-clear-symbolic")
        clear_btn.set_tooltip_text("Clear all filters")
        clear_btn.add_css_class("flat")
        clear_btn.connect("clicked", self._on_clear_filters)
        self.filter_bar.append(clear_btn)

        separator = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        self.filter_bar.append(separator)

        self._add_system_filters()

        return self.filter_bar

    def _add_system_filters(self):
        """Add system content type filter buttons."""
        self.system_filter_chips = []
        system_filters = [
            ("text", "Text", "text-x-generic-symbolic"),
            ("file", "File", "document-save-symbolic"),
            ("image", "Image", "image-x-generic-symbolic"),
            ("url", "URL", "web-browser-symbolic"),
        ]

        for filter_id, label, icon_name in system_filters:
            chip = Gtk.ToggleButton()
            chip_box = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=4
            )

            icon = Gtk.Image.new_from_icon_name(icon_name)
            icon.set_pixel_size(16)
            chip_box.append(icon)

            label_widget = Gtk.Label(label=label)
            chip_box.append(label_widget)

            chip.set_child(chip_box)
            chip.add_css_class("pill")
            chip.connect(
                "toggled",
                lambda btn, fid=filter_id: self._on_filter_toggled(fid, btn),
            )

            self.filter_box.append(chip)
            self.system_filter_chips.append(chip)

    def _on_filter_toggled(self, filter_id: str, button: Gtk.ToggleButton):
        """Handle filter chip toggle."""
        if button.get_active():
            self.active_filters.add(filter_id)
        else:
            self.active_filters.discard(filter_id)

        print(
            f"[FILTER] Toggled filter '{filter_id}', "
            f"active: {button.get_active()}"
        )
        print(f"[FILTER] Current active filters: {self.active_filters}")

        self.on_filter_change()

    def _on_clear_filters(self, button: Gtk.Button):
        """Clear all active filters."""
        self.active_filters.clear()

        for flow_child in list(self.filter_box):
            chip = flow_child.get_child()
            if isinstance(chip, Gtk.ToggleButton):
                chip.set_active(False)

        self.on_filter_change()

    def get_active_filters(self) -> Set[str]:
        """Get the currently active filters."""
        return self.active_filters

    def set_visible(self, visible: bool):
        """Set filter bar visibility."""
        if self.filter_bar:
            self.filter_bar.set_visible(visible)
