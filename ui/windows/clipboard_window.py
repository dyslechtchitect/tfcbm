"""ClipboardWindow - Main application window.

This is the original 2,300-line implementation.
To be refactored into focused classes.
"""

import asyncio
import json
import logging
import os
import re
import signal
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path

import gi
import websockets

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Gio", "2.0")

from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from settings import get_settings
from ui.about import AboutWindow
from ui.managers.tab_manager import TabManager
from ui.rows.clipboard_item_row import ClipboardItemRow

logger = logging.getLogger("TFCBM.UI")


def highlight_text(text, query):
    """Highlight matching text with yellow background using Pango markup."""
    if not query or not text:
        return GLib.markup_escape_text(text) if text else ""

    escaped_text = GLib.markup_escape_text(text)
    escaped_query = re.escape(query)

    def replace_match(match):
        return f'<span background="yellow" foreground="black">{match.group(0)}</span>'

    highlighted = re.sub(
        f"({escaped_query})", replace_match, escaped_text, flags=re.IGNORECASE
    )
    return highlighted


class ClipboardWindow(Adw.ApplicationWindow):
    """Main application window"""

    def __init__(self, app, server_pid=None):
        start_time = time.time()
        logger.info("Initializing ClipboardWindow...")
        super().__init__(application=app, title="TFCBM")
        self.server_pid = server_pid

        # Track if window was activated via keyboard shortcut (Ctrl+`)
        self.activated_via_keyboard = False

        # Load settings
        self.settings = get_settings()

        # Initialize password service for secrets
        from ui.services.password_service import PasswordService
        self.password_service = PasswordService()

        # Connect close request handler
        self.connect("close-request", self._on_close_request)

        # Connect focus change handler to clear secret authentication
        self.connect("notify::is-active", self._on_focus_changed)

        # Set window properties
        display = Gdk.Display.get_default()
        if display:
            monitors = display.get_monitors()
            if monitors and monitors.get_n_items() > 0:
                primary_monitor = monitors.get_item(0)
                monitor_geometry = primary_monitor.get_geometry()
                width = monitor_geometry.width // 3
                self.set_default_size(width, 800)
            else:
                self.set_default_size(350, 800)
        else:
            self.set_default_size(350, 800)

        self.set_resizable(True)

        # Position window to the left
        self.position_window_left()

        # Pagination state
        self.copied_offset = 0
        self.copied_total = 0
        self.copied_has_more = True
        self.copied_loading = False

        self.pasted_offset = 0
        self.pasted_total = 0
        self.pasted_has_more = True
        self.pasted_loading = False

        self.page_size = self.settings.max_page_length

        # Sort state
        self.copied_sort_order = "DESC"  # Default: newest first
        self.pasted_sort_order = "DESC"  # Default: newest first

        # Window icon is set through the desktop file and application
        # GTK4/Adwaita doesn't use set_icon() anymore

        # Create main box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        self.header = Adw.HeaderBar()
        self.header.add_css_class("tfcbm-header")

        # Title stack
        self.title_stack = Gtk.Stack()
        self.header.set_title_widget(self.title_stack)

        self.title_label = Gtk.Label(label="TFCBM")
        self.title_label.add_css_class("title")
        self.title_label.add_css_class("tfcbm-title")
        self.title_stack.add_named(self.title_label, "main")

        self.settings_title_label = Gtk.Label(label="Settings")
        self.settings_title_label.add_css_class("title")
        self.settings_title_label.add_css_class("tfcbm-title")
        self.title_stack.add_named(self.settings_title_label, "settings")

        # Button stack
        self.button_stack = Gtk.Stack()
        self.header.pack_end(self.button_stack)

        main_buttons = Gtk.Box()
        info_button = Gtk.Button()
        info_button.set_icon_name("help-about-symbolic")
        info_button.add_css_class("flat")
        info_button.connect("clicked", self._show_splash_screen)
        main_buttons.append(info_button)

        settings_button = Gtk.Button()
        settings_button.set_icon_name("emblem-system-symbolic")
        settings_button.add_css_class("flat")
        settings_button.connect("clicked", self._show_settings_page)
        main_buttons.append(settings_button)
        self.button_stack.add_named(main_buttons, "main")

        settings_buttons = Gtk.Box()
        back_button = Gtk.Button()
        back_button.set_icon_name("go-previous-symbolic")
        back_button.add_css_class("flat")
        back_button.connect("clicked", self._show_tabs_page)
        settings_buttons.append(back_button)
        self.button_stack.add_named(settings_buttons, "settings")

        main_box.append(self.header)

        # Search bar container
        self.search_container = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=6
        )
        self.search_container.set_margin_start(8)
        self.search_container.set_margin_end(8)
        self.search_container.set_margin_top(8)
        self.search_container.set_margin_bottom(4)

        # Search entry
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_hexpand(True)
        self.search_entry.set_placeholder_text("Search clipboard items...")
        self.search_entry.connect("search-changed", self._on_search_changed)
        self.search_entry.connect("activate", self._on_search_activate)
        self.search_container.append(self.search_entry)

        main_box.append(self.search_container)

        # Tag filter area
        tag_frame = Gtk.Frame()
        tag_frame.set_margin_start(8)
        tag_frame.set_margin_end(8)
        tag_frame.set_margin_top(4)
        tag_frame.set_margin_bottom(4)
        tag_frame.add_css_class("view")

        # Minimal tag container - just tags and a small X
        tag_container = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=4
        )
        tag_container.set_margin_top(4)
        tag_container.set_margin_bottom(4)
        tag_container.set_margin_start(8)
        tag_container.set_margin_end(8)

        # Scrollable tag area with FlowBox for tag buttons
        tag_scrolled = Gtk.ScrolledWindow()
        tag_scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.NEVER)
        tag_scrolled.set_max_content_height(40)
        tag_scrolled.set_min_content_height(32)
        tag_scrolled.set_propagate_natural_height(True)
        tag_scrolled.set_hexpand(True)

        self.tag_flowbox = Gtk.FlowBox()
        self.tag_flowbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.tag_flowbox.set_homogeneous(False)
        self.tag_flowbox.set_column_spacing(4)
        self.tag_flowbox.set_row_spacing(4)
        self.tag_flowbox.set_max_children_per_line(15)
        tag_scrolled.set_child(self.tag_flowbox)

        tag_container.append(tag_scrolled)

        # Small X button to clear filter
        clear_btn = Gtk.Button()
        clear_btn.set_icon_name("window-close-symbolic")
        clear_btn.add_css_class("flat")
        clear_btn.set_tooltip_text("Clear filter")
        clear_btn.set_valign(Gtk.Align.CENTER)
        # Make it very small
        css_provider = Gtk.CssProvider()
        css_data = (
            "button { min-width: 20px; min-height: 20px; padding: 2px; }"
        )
        css_provider.load_from_data(css_data.encode())
        clear_btn.get_style_context().add_provider(
            css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        clear_btn.connect("clicked", lambda btn: self._clear_tag_filter())
        tag_container.append(clear_btn)
        tag_frame.set_child(tag_container)

        # Create a stack to manage main content (tabs vs settings)
        self.main_stack = Gtk.Stack()
        self.main_stack.set_transition_type(
            Gtk.StackTransitionType.SLIDE_LEFT_RIGHT
        )

        # Create TabView for Recently Copied and Recently Pasted
        self.tab_view = Adw.TabView()
        self.tab_view.set_vexpand(True)
        self.main_stack.add_named(self.tab_view, "tabs")

        # Prevent tabs from being closed by the user
        self.tab_view.connect("close-page", self._on_close_page)

        # Tab bar
        self.tab_bar = Adw.TabBar()
        self.tab_bar.set_view(self.tab_view)
        main_box.append(self.tab_bar)

        # Create filter bar (will be added to toolbar later)
        self._create_filter_bar()

        # Tab 1: Recently Copied
        copied_scrolled = Gtk.ScrolledWindow()
        copied_scrolled.set_vexpand(True)
        copied_scrolled.set_policy(
            Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC
        )
        self.copied_scrolled = copied_scrolled

        copied_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        # BOTTOM footer with status label
        copied_footer = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=6
        )
        copied_footer.set_margin_top(8)
        copied_footer.set_margin_bottom(4)
        copied_footer.set_margin_start(8)
        copied_footer.set_margin_end(8)

        # Status label for copied items
        self.copied_status_label = Gtk.Label()
        self.copied_status_label.add_css_class("dim-label")
        self.copied_status_label.add_css_class("caption")
        self.copied_status_label.set_hexpand(True)
        self.copied_status_label.set_halign(Gtk.Align.START)
        copied_footer.append(self.copied_status_label)

        self.copied_listbox = Gtk.ListBox()
        self.copied_listbox.add_css_class("boxed-list")
        self.copied_listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        copied_box.append(self.copied_listbox)

        # Loader for copied items
        self.copied_loader = self._create_loader()
        self.copied_loader.set_visible(False)
        copied_box.append(self.copied_loader)

        # Footer with status label (at bottom)
        copied_box.append(copied_footer)

        copied_scrolled.set_child(copied_box)

        # Connect scroll event for infinite scroll
        copied_vadj = copied_scrolled.get_vadjustment()
        copied_vadj.connect(
            "value-changed", lambda adj: self._on_scroll_changed(adj, "copied")
        )

        copied_page = self.tab_view.append(copied_scrolled)
        copied_page.set_title("Recently Copied")
        copied_page.set_icon(Gio.ThemedIcon.new("edit-copy-symbolic"))
        copied_page.set_indicator_icon(None)  # Remove close button by clearing indicator

        # Tab 2: Recently Pasted
        pasted_scrolled = Gtk.ScrolledWindow()
        pasted_scrolled.set_vexpand(True)
        pasted_scrolled.set_policy(
            Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC
        )
        self.pasted_scrolled = pasted_scrolled

        pasted_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        # Sticky filter bar at top (shared with copied tab)

        # BOTTOM footer with status label
        pasted_footer = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=6
        )
        pasted_footer.set_margin_top(8)
        pasted_footer.set_margin_bottom(4)
        pasted_footer.set_margin_start(8)
        pasted_footer.set_margin_end(8)

        # Status label for pasted items
        self.pasted_status_label = Gtk.Label()
        self.pasted_status_label.add_css_class("dim-label")
        self.pasted_status_label.add_css_class("caption")
        self.pasted_status_label.set_hexpand(True)
        self.pasted_status_label.set_halign(Gtk.Align.START)
        pasted_footer.append(self.pasted_status_label)

        self.pasted_listbox = Gtk.ListBox()
        self.pasted_listbox.add_css_class("boxed-list")
        self.pasted_listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        pasted_box.append(self.pasted_listbox)

        # Loader for pasted items
        self.pasted_loader = self._create_loader()
        self.pasted_loader.set_visible(False)
        pasted_box.append(self.pasted_loader)

        # Footer with status label (at bottom)
        pasted_box.append(pasted_footer)

        pasted_scrolled.set_child(pasted_box)

        # Connect scroll event for infinite scroll
        pasted_vadj = pasted_scrolled.get_vadjustment()
        pasted_vadj.connect(
            "value-changed", lambda adj: self._on_scroll_changed(adj, "pasted")
        )

        pasted_page = self.tab_view.append(pasted_scrolled)
        pasted_page.set_title("Recently Pasted")
        pasted_page.set_icon(Gio.ThemedIcon.new("edit-paste-symbolic"))
        pasted_page.set_indicator_icon(None)  # Remove close button by clearing indicator

        # Create settings page
        settings_page = self._create_settings_page()
        self.main_stack.add_named(settings_page, "settings")

        # Tab 4: Tag Manager
        tag_manager_scrolled = Gtk.ScrolledWindow()
        tag_manager_scrolled.set_vexpand(True)
        tag_manager_scrolled.set_policy(
            Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC
        )

        # Create tag manager page
        tag_manager_page = Adw.PreferencesPage()

        # Tags List Group
        tags_group = Adw.PreferencesGroup()
        tags_group.set_title("User-Defined Tags")
        tags_group.set_description(
            "Manage your custom tags for organizing clipboard items"
        )

        # Add a "Create New Tag" button at the top
        create_tag_row = Adw.ActionRow()
        create_tag_row.set_title("Create New Tag")
        create_tag_row.set_subtitle(
            "Add a new tag to organize your clipboard items"
        )

        create_tag_button = Gtk.Button()
        create_tag_button.set_label("New Tag")
        create_tag_button.add_css_class("suggested-action")
        create_tag_button.set_valign(Gtk.Align.CENTER)
        create_tag_button.connect("clicked", self._on_create_tag)
        create_tag_row.add_suffix(create_tag_button)

        tags_group.add(create_tag_row)
        tag_manager_page.add(tags_group)

        # User tags list group
        self.user_tags_group = Adw.PreferencesGroup()
        self.user_tags_group.set_title("Your Tags")
        tag_manager_page.add(self.user_tags_group)

        tag_manager_scrolled.set_child(tag_manager_page)

        tag_manager_tab = self.tab_view.append(tag_manager_scrolled)
        tag_manager_tab.set_title("Tags")
        tag_manager_tab.set_icon(Gio.ThemedIcon.new("tag-symbolic"))

        # Connect tab switch event
        self.tab_view.connect("notify::selected-page", self._on_tab_switched)

        # Add sticky filter bar (contains filters, sort, jump)
        main_box.append(self.filter_bar)
        print(
            f"[DEBUG] Filter bar added to main_box, visible: {self.filter_bar.get_visible()}",
            flush=True,
        )
        print(
            f"[DEBUG] Filter toggle button visible: {self.filter_toggle_btn.get_visible()}",
            flush=True,
        )
        print(
            f"[DEBUG] Filter bar has {len(list(self.filter_bar))} children",
            flush=True,
        )

        main_box.append(self.main_stack)

        # Add tag filter at the bottom (footer)
        main_box.append(tag_frame)

        # NEW: Notification area
        self.notification_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.notification_box.set_vexpand(False)
        self.notification_box.set_hexpand(True)
        self.notification_box.set_halign(Gtk.Align.FILL)
        self.notification_box.set_valign(Gtk.Align.END)
        self.notification_box.set_size_request(-1, 30)  # Narrow strip
        self.notification_box.add_css_class("notification-area")
        self.notification_label = Gtk.Label(label="")
        self.notification_label.set_hexpand(True)
        self.notification_label.set_halign(Gtk.Align.CENTER)
        self.notification_label.set_valign(Gtk.Align.CENTER)
        self.notification_label.add_css_class(
            "marquee-text"
        )  # Add marquee-text class
        self.notification_box.append(self.notification_label)
        main_box.append(self.notification_box)

        # Set up main box as content
        self.set_content(main_box)

        # Load clipboard history
        GLib.idle_add(self.load_history)

        # Store current tab state
        self.current_tab = "copied"

        # Search state
        self.search_query = ""
        self.search_timer = None
        self.search_active = False
        self.search_results = []

        # Initialize TabManager
        self.tab_manager = TabManager(
            window_instance=self,
            filter_bar=self.filter_bar,
        )

        # Tag state
        self.all_tags = []  # All available tags (system + user)
        self.selected_tag_ids = []  # Currently selected tag IDs for filtering
        self.tag_buttons = {}  # Dict of tag_id -> button widget
        self.filter_active = False  # Track if tag filtering is active
        self.filtered_items = []  # Filtered items when tag filter is active
        self.dragged_tag = None

        # Position window to the left
        self.position_window_left()

        # Set up global keyboard shortcut

        # Load tags for filtering
        self.load_tags()

        # Load user tags for tag manager
        self.load_user_tags()

        # Add keyboard event controller for Return/Space quick copy
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_controller)

        logger.info(
            f"ClipboardWindow initialized in {time.time() - start_time:.2f} seconds"
        )

    def position_window_left(self):
        """Position window to the left side of the screen"""
        display = Gdk.Display.get_default()
        if display:
            surface = self.get_surface()
            if surface:
                # Move to left edge
                surface.toplevel_move(0, 0)

    def _focus_first_item(self):
        """Focus the first item in the current tab's list when opened via keyboard shortcut"""
        try:
            # Get the first row from the copied listbox (Recently Copied tab)
            first_row = self.copied_listbox.get_row_at_index(0)
            if first_row:
                # Set focus to the first row
                first_row.grab_focus()
                logger.info("[KEYBOARD] Auto-focused first item in list")
                return False  # Don't repeat
            else:
                logger.warning("[KEYBOARD] No items to focus")
                return False
        except Exception as e:
            logger.error(f"[KEYBOARD] Error focusing first item: {e}")
            return False

    def _on_key_pressed(self, controller, keyval, keycode, state):
        """Handle keyboard shortcuts: Return/Space to copy item, alphanumeric to focus search"""
        # Get the currently focused widget
        focused_widget = self.get_focus()

        # Feature 1: Auto-focus search bar on alphanumeric keypress
        # Check if this is an alphanumeric key (a-z, A-Z, 0-9)
        is_alphanumeric = False
        if (
            Gdk.KEY_a <= keyval <= Gdk.KEY_z
            or Gdk.KEY_A <= keyval <= Gdk.KEY_Z
            or Gdk.KEY_0 <= keyval <= Gdk.KEY_9
        ):
            is_alphanumeric = True

        # If alphanumeric and search bar is NOT focused, focus it and let the key be typed
        if is_alphanumeric:
            if focused_widget != self.search_entry:
                logger.info(
                    f"[KEYBOARD] Auto-focusing search bar on alphanumeric key"
                )
                self.search_entry.grab_focus()
                # Return False to let the key event propagate to the search entry
                return False

        # Handle Return/Space key press to copy item
        if keyval not in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_space):
            return False  # Let other handlers process this key

        if not focused_widget:
            return False

        # Find the ClipboardItemRow - it might be the focused widget or a parent
        row = focused_widget
        max_depth = 10  # Prevent infinite loop
        while row and max_depth > 0:
            if isinstance(row, ClipboardItemRow):
                # Found the row! Copy it
                logger.info(
                    f"[KEYBOARD] Copying item {row.item.get('id')} via keyboard"
                )
                row._on_row_clicked(row)

                # If activated via keyboard shortcut, hide window and paste
                if self.activated_via_keyboard:
                    logger.info("[KEYBOARD] Auto-pasting and hiding window")
                    # Hide window first
                    self.hide()
                    self.activated_via_keyboard = False  # Clear flag

                    # Give the window time to hide and focus to return
                    def simulate_paste():
                        import shutil
                        import subprocess

                        # Try xdotool first (X11)
                        if shutil.which("xdotool"):
                            try:
                                subprocess.run(
                                    ["xdotool", "key", "ctrl+v"],
                                    check=False,
                                    timeout=2,
                                )
                                logger.info(
                                    "[KEYBOARD] Simulated Ctrl+V paste with xdotool"
                                )
                                return False
                            except Exception as e:
                                logger.error(f"[KEYBOARD] xdotool failed: {e}")

                        # Try ydotool (Wayland)
                        if shutil.which("ydotool"):
                            try:
                                # ydotool uses different key codes: 29=Ctrl, 47=v
                                subprocess.run(
                                    [
                                        "ydotool",
                                        "key",
                                        "29:1",
                                        "47:1",
                                        "47:0",
                                        "29:0",
                                    ],
                                    check=False,
                                    timeout=2,
                                )
                                logger.info(
                                    "[KEYBOARD] Simulated Ctrl+V paste with ydotool"
                                )
                                return False
                            except Exception as e:
                                logger.error(f"[KEYBOARD] ydotool failed: {e}")

                        # No tool available
                        logger.warning(
                            "[KEYBOARD] Neither xdotool nor ydotool found. Auto-paste disabled."
                        )
                        logger.warning(
                            "[KEYBOARD] Install xdotool: sudo dnf install xdotool"
                        )
                        return False

                    # Wait a bit for focus to return, then paste
                    GLib.timeout_add(150, simulate_paste)

                return True  # Event handled

            # Try parent widget
            row = row.get_parent()
            max_depth -= 1

        return False  # Not a clipboard row, let other handlers process

    def load_history(self):
        """Load clipboard history and listen for updates via WebSocket"""
        self.history_load_start_time = time.time()
        logger.info("Starting initial history load...")

        def run_websocket():
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.websocket_client())
            finally:
                loop.close()

        # Run in background thread
        thread = threading.Thread(target=run_websocket, daemon=True)
        thread.start()

    async def websocket_client(self):
        """WebSocket client to connect to backend"""
        uri = "ws://localhost:8765"
        max_size = 5 * 1024 * 1024  # 5MB to match server
        print(f"Connecting to WebSocket server at {uri}...")

        try:
            async with websockets.connect(uri, max_size=max_size) as websocket:
                print("Connected to WebSocket server")

                # Request history
                request = {"action": "get_history", "limit": self.page_size}
                if self.active_filters:
                    request["filters"] = list(self.active_filters)
                    print(
                        f"[FILTER] Sending filters to server: {list(self.active_filters)}"
                    )
                await websocket.send(json.dumps(request))
                print(
                    f"Requested history with filters: {request.get('filters', 'none')}"
                )

                # Listen for messages
                async for message in websocket:
                    data = json.loads(message)
                    msg_type = data.get("type")

                    if msg_type == "history":
                        # Initial history load
                        items = data.get("items", [])
                        total_count = data.get("total_count", 0)
                        offset = data.get("offset", 0)
                        print(
                            f"Received {len(items)} items from history (total: {total_count})"
                        )
                        GLib.idle_add(
                            self._initial_history_load,
                            items,
                            total_count,
                            offset,
                        )

                    elif msg_type == "recently_pasted":
                        # Pasted history load
                        items = data.get("items", [])
                        total_count = data.get("total_count", 0)
                        offset = data.get("offset", 0)
                        print(
                            f"Received {len(items)} pasted items (total: {total_count})"
                        )
                        GLib.idle_add(
                            self._initial_pasted_load,
                            items,
                            total_count,
                            offset,
                        )

                    elif msg_type == "new_item":
                        # New item added
                        item = data.get("item")
                        if item:
                            print(f"New item received: {item['type']}")
                            GLib.idle_add(self.add_item, item)

                    elif msg_type == "item_deleted":
                        # Item deleted
                        item_id = data.get("id")
                        if item_id:
                            GLib.idle_add(self.remove_item, item_id)

        except websockets.exceptions.ConnectionClosedError:
            # Normal closure when app exits - suppress error
            print("WebSocket connection closed")
        except Exception as e:
            print(f"WebSocket error: {e}")
            traceback.print_exc()
            GLib.idle_add(self.show_error, str(e))

    def load_pasted_history(self):
        """Load recently pasted items via WebSocket"""
        page_size = self.page_size  # Capture for closure

        def run_websocket():
            try:

                async def get_pasted():
                    uri = "ws://localhost:8765"
                    max_size = 5 * 1024 * 1024  # 5MB
                    async with websockets.connect(
                        uri, max_size=max_size
                    ) as websocket:
                        # Request pasted history
                        request = {
                            "action": "get_recently_pasted",
                            "limit": page_size,
                        }
                        # Include active filters
                        if self.active_filters:
                            request["filters"] = list(self.active_filters)
                            print(
                                f"[FILTER] Requesting pasted items with filters: {list(self.active_filters)}"
                            )
                        await websocket.send(json.dumps(request))

                        # Wait for response
                        response = await websocket.recv()
                        data = json.loads(response)

                        if data.get("type") == "recently_pasted":
                            items = data.get("items", [])
                            print(f"Received {len(items)} pasted items")
                            GLib.idle_add(self.update_pasted_history, items)

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(get_pasted())
                finally:
                    loop.close()

            except Exception as e:
                print(f"Error loading pasted history: {e}")

        # Run in background thread
        thread = threading.Thread(target=run_websocket, daemon=True)
        thread.start()

    def _create_loader(self):
        """Create an animated loader using the TFCBM loader.svg"""
        # Load the animated SVG loader
        loader_path = Path(__file__).parent.parent / "resouces" / "loader.svg"

        if loader_path.exists():
            # Create a Picture widget to display the SVG
            picture = Gtk.Picture.new_for_filename(str(loader_path))
            picture.set_size_request(120, 120)  # SVG is 120x120
            picture.set_halign(Gtk.Align.CENTER)
            picture.set_valign(Gtk.Align.CENTER)
            picture.set_can_shrink(False)
            return picture
        else:
            # Fallback to spinner if SVG not found
            spinner = Gtk.Spinner()
            spinner.set_size_request(24, 24)
            spinner.set_halign(Gtk.Align.CENTER)
            spinner.set_valign(Gtk.Align.CENTER)
            spinner.start()
            return spinner

    def update_history(self, history):
        """Update the copied listbox with history items"""
        # Clear existing items
        while True:
            row = self.copied_listbox.get_row_at_index(0)
            if row is None:
                break
            self.copied_listbox.remove(row)

        # Add items (already in reverse order from backend)
        for item in history:
            row = ClipboardItemRow(item, self, search_query=self.search_query)
            self.copied_listbox.prepend(row)  # Add to top

        return False  # Don't repeat

    def update_pasted_history(self, history):
        """Update the pasted listbox with pasted items"""
        # Clear existing items
        while True:
            row = self.pasted_listbox.get_row_at_index(0)
            if row is None:
                break
            self.pasted_listbox.remove(row)

        # Add items (database returns DESC order, append to maintain it)
        for item in history:
            row = ClipboardItemRow(
                item,
                self,
                show_pasted_time=True,
                search_query=self.search_query,
            )
            self.pasted_listbox.append(row)  # Append to maintain DESC order

        return False  # Don't repeat

    def _initial_history_load(self, items, total_count, offset):
        """Initial load of copied history with pagination data"""
        if hasattr(self, "history_load_start_time"):
            duration = time.time() - self.history_load_start_time
            logger.info(f"Initial history loaded in {duration:.2f} seconds")
            del self.history_load_start_time

        # Update pagination state
        self.copied_offset = offset
        self.copied_total = total_count
        self.copied_has_more = (offset + len(items)) < total_count

        # Clear existing items
        while True:
            row = self.copied_listbox.get_row_at_index(0)
            if row is None:
                break
            self.copied_listbox.remove(row)

        # Add items (database returns DESC order, append to maintain it)
        for item in items:
            row = ClipboardItemRow(item, self, search_query=self.search_query)
            self.copied_listbox.append(row)  # Append to maintain DESC order

        # Update status label
        current_count = len(items)
        self.copied_status_label.set_label(
            f"Showing {current_count} of {total_count} items"
        )

        # Kill standalone splash screen and show main window
        subprocess.run(
            ["pkill", "-f", "ui/splash.py"], stderr=subprocess.DEVNULL
        )
        self.present()

        return False  # Don't repeat

    def _initial_pasted_load(self, items, total_count, offset):
        """Initial load of pasted history with pagination data"""
        # Update pagination state
        self.pasted_offset = offset
        self.pasted_total = total_count
        self.pasted_has_more = (offset + len(items)) < total_count

        # Clear existing items
        while True:
            row = self.pasted_listbox.get_row_at_index(0)
            if row is None:
                break
            self.pasted_listbox.remove(row)

        # Add items (database returns DESC order, append to maintain it)
        for item in items:
            row = ClipboardItemRow(
                item,
                self,
                show_pasted_time=True,
                search_query=self.search_query,
            )
            self.pasted_listbox.append(row)  # Append to maintain DESC order

        # Update status label
        current_count = len(items)
        self.pasted_status_label.set_label(
            f"Showing {current_count} of {total_count} items"
        )

        # Scroll to top
        vadj = self.pasted_scrolled.get_vadjustment()
        vadj.set_value(0)

        return False  # Don't repeat

    def add_item(self, item):
        """Add a single new item to the top of the copied list"""
        row = ClipboardItemRow(item, self)
        self.copied_listbox.prepend(row)
        # Force the listbox to redraw
        self.copied_listbox.queue_draw()
        # Update the total count
        self.copied_total_count = (
            self.copied_total_count + 1
            if hasattr(self, "copied_total_count")
            else 1
        )
        self._update_copied_status()
        return False

    def _update_copied_status(self):
        """Update the copied items status label"""
        # Count current items in listbox
        current_count = 0
        index = 0
        while True:
            row = self.copied_listbox.get_row_at_index(index)
            if row is None:
                break
            current_count += 1
            index += 1

        # Update status label
        total = getattr(self, "copied_total_count", current_count)
        self.copied_status_label.set_label(
            f"Showing {current_count} of {total} items"
        )

    def remove_item(self, item_id):
        """Remove an item from both lists by ID"""
        # Remove from copied list
        index = 0
        while True:
            row = self.copied_listbox.get_row_at_index(index)
            if row is None:
                break
            if hasattr(row, "item") and row.item.get("id") == item_id:
                self.copied_listbox.remove(row)
                break
            index += 1

        # Remove from pasted list
        index = 0
        while True:
            row = self.pasted_listbox.get_row_at_index(index)
            if row is None:
                break
            if hasattr(row, "item") and row.item.get("id") == item_id:
                self.pasted_listbox.remove(row)
                break
            index += 1

        return False

    def show_error(self, error_msg):
        """Show error message"""
        error_label = Gtk.Label(label=f"Error: {error_msg}")
        error_label.add_css_class("error")
        error_label.set_selectable(True)  # Make error copyable
        error_label.set_wrap(True)
        self.copied_listbox.append(error_label)
        return False

    def show_notification(self, message):
        """Show a notification message in the dedicated area"""
        logger.debug(f"Showing notification: {message}")
        self.notification_label.set_label(message)
        self.notification_box.set_visible(True)

        logger.debug(
            f"Notification box visible: {self.notification_box.get_visible()}"
        )
        logger.debug(
            f"Notification label visible: {self.notification_label.get_visible()}"
        )
        logger.debug(
            f"Notification box height: {self.notification_box.get_height()}"
        )

        # Check if message is long enough for marquee
        if len(message) > 50:  # Arbitrary threshold, can be adjusted
            self.notification_label.add_css_class("animate-marquee")
        else:
            self.notification_label.remove_css_class("animate-marquee")

        # Hide after a few seconds
        GLib.timeout_add_seconds(10, self._hide_notification)

    def _hide_notification(self):
        """Hide the notification area"""
        self.notification_box.set_visible(False)
        self.notification_label.set_label("")
        self.notification_label.remove_css_class(
            "animate-marquee"
        )  # Remove marquee class
        return GLib.SOURCE_REMOVE  # Only run once

    def _on_tab_switched(self, tab_view, param):
        """Handle tab switching - delegates to TabManager"""
        self.tab_manager.handle_tab_switched(tab_view, param)
        # Update window's current_tab to match TabManager
        self.current_tab = self.tab_manager.current_tab

    def _jump_to_top(self, list_type):
        """Scroll to the top of the specified list"""
        if list_type == "copied":
            vadj = self.copied_scrolled.get_vadjustment()
            vadj.set_value(0)
        elif list_type == "pasted":
            vadj = self.pasted_scrolled.get_vadjustment()
            vadj.set_value(0)

    def _toggle_sort_from_toolbar(self):
        """Toggle sort for the currently active tab"""
        # Determine which tab is active
        if self.current_tab == "copied":
            self._toggle_sort("copied")
        else:
            self._toggle_sort("pasted")

    def _jump_to_top_from_toolbar(self):
        """Jump to top for the currently active tab"""
        if self.current_tab == "copied":
            self._jump_to_top("copied")
        else:
            self._jump_to_top("pasted")

    def _toggle_sort(self, list_type):
        """Toggle sort order for the specified list"""
        if list_type == "copied":
            # Toggle sort order
            self.copied_sort_order = (
                "ASC" if self.copied_sort_order == "DESC" else "DESC"
            )

            # Update toolbar button icon and tooltip
            if self.copied_sort_order == "DESC":
                self.filter_sort_btn.set_icon_name(
                    "view-sort-descending-symbolic"
                )
                self.filter_sort_btn.set_tooltip_text("Newest first ↓")
            else:
                self.filter_sort_btn.set_icon_name(
                    "view-sort-ascending-symbolic"
                )
                self.filter_sort_btn.set_tooltip_text("Oldest first ↑")

            # Reload data with new sort order
            self._reload_copied_with_sort()

        elif list_type == "pasted":
            # Toggle sort order
            self.pasted_sort_order = (
                "ASC" if self.pasted_sort_order == "DESC" else "DESC"
            )

            # Update toolbar button icon and tooltip
            if self.pasted_sort_order == "DESC":
                self.filter_sort_btn.set_icon_name(
                    "view-sort-descending-symbolic"
                )
                self.filter_sort_btn.set_tooltip_text("Newest first ↓")
            else:
                self.filter_sort_btn.set_icon_name(
                    "view-sort-ascending-symbolic"
                )
                self.filter_sort_btn.set_tooltip_text("Oldest first ↑")

            # Reload data with new sort order
            self._reload_pasted_with_sort()

    def _reload_copied_with_sort(self):
        """Reload copied items with current sort order"""

        def reload():
            try:

                async def get_sorted_history():
                    uri = "ws://localhost:8765"
                    max_size = 5 * 1024 * 1024
                    async with websockets.connect(
                        uri, max_size=max_size
                    ) as websocket:
                        request = {
                            "action": "get_history",
                            "limit": self.page_size,
                            "sort_order": self.copied_sort_order,
                        }
                        if self.active_filters:
                            request["filters"] = list(self.active_filters)
                        await websocket.send(json.dumps(request))
                        response = await websocket.recv()
                        data = json.loads(response)

                        if data.get("type") == "history":
                            items = data.get("items", [])
                            total_count = data.get("total_count", 0)
                            offset = data.get("offset", 0)
                            GLib.idle_add(
                                self._initial_history_load,
                                items,
                                total_count,
                                offset,
                            )

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(get_sorted_history())
                finally:
                    loop.close()
            except Exception as e:
                print(f"[UI] Error reloading sorted history: {e}")

        threading.Thread(target=reload, daemon=True).start()

    def _reload_pasted_with_sort(self):
        """Reload pasted items with current sort order"""

        def reload():
            try:

                async def get_sorted_pasted():
                    uri = "ws://localhost:8765"
                    max_size = 5 * 1024 * 1024
                    async with websockets.connect(
                        uri, max_size=max_size
                    ) as websocket:
                        request = {
                            "action": "get_recently_pasted",
                            "limit": self.page_size,
                            "sort_order": self.pasted_sort_order,
                        }
                        # Include active filters
                        if self.active_filters:
                            request["filters"] = list(self.active_filters)
                        await websocket.send(json.dumps(request))
                        response = await websocket.recv()
                        data = json.loads(response)

                        if data.get("type") == "recently_pasted":
                            items = data.get("items", [])
                            total_count = data.get("total_count", 0)
                            offset = data.get("offset", 0)
                            GLib.idle_add(
                                self._initial_pasted_load,
                                items,
                                total_count,
                                offset,
                            )

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(get_sorted_pasted())
                finally:
                    loop.close()
            except Exception as e:
                print(f"[UI] Error reloading sorted pasted: {e}")

        threading.Thread(target=reload, daemon=True).start()

    def _on_scroll_changed(self, adjustment, list_type):
        """Handle scroll events for infinite scrolling"""
        # Don't load more items if search is active - search results are complete
        if self.search_active:
            return

        if (
            adjustment.get_upper()
            - adjustment.get_page_size()
            - adjustment.get_value()
            < 50
        ):  # 50 pixels from bottom
            if (
                list_type == "copied"
                and self.copied_has_more
                and not self.copied_loading
            ):
                print(
                    "[UI] Scrolled to bottom of copied list, loading more..."
                )
                self.copied_loading = True
                self.copied_loader.set_visible(True)
                GLib.idle_add(self._load_more_copied_items)
            elif (
                list_type == "pasted"
                and self.pasted_has_more
                and not self.pasted_loading
            ):
                print(
                    "[UI] Scrolled to bottom of pasted list, loading more..."
                )
                self.pasted_loading = True
                self.pasted_loader.set_visible(True)
                GLib.idle_add(self._load_more_pasted_items)

    def _load_more_copied_items(self):
        """Load more copied items via WebSocket"""

        def run_websocket():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._fetch_more_items("copied"))
            finally:
                loop.close()

        threading.Thread(target=run_websocket, daemon=True).start()
        return False

    def _load_more_pasted_items(self):
        """Load more pasted items via WebSocket"""

        def run_websocket():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._fetch_more_items("pasted"))
            finally:
                loop.close()

        threading.Thread(target=run_websocket, daemon=True).start()
        return False

    async def _fetch_more_items(self, list_type):
        """Fetch more items from backend via WebSocket"""
        uri = "ws://localhost:8765"
        max_size = 5 * 1024 * 1024  # 5MB
        try:
            async with websockets.connect(uri, max_size=max_size) as websocket:
                if list_type == "copied":
                    request = {
                        "action": "get_history",
                        "offset": self.copied_offset + self.page_size,
                        "limit": self.page_size,
                    }
                    if self.active_filters:
                        request["filters"] = list(self.active_filters)
                else:  # pasted
                    request = {
                        "action": "get_recently_pasted",
                        "offset": self.pasted_offset + self.page_size,
                        "limit": self.page_size,
                    }
                    # Include active filters for pasted items too
                    if self.active_filters:
                        request["filters"] = list(self.active_filters)

                await websocket.send(json.dumps(request))
                response = await websocket.recv()
                data = json.loads(response)

                if data.get("type") == "history" and list_type == "copied":
                    items = data.get("items", [])
                    total_count = data.get("total_count", 0)
                    offset = data.get("offset", 0)
                    GLib.idle_add(
                        self._append_items_to_listbox,
                        items,
                        total_count,
                        offset,
                        "copied",
                    )
                elif (
                    data.get("type") == "recently_pasted"
                    and list_type == "pasted"
                ):
                    items = data.get("items", [])
                    total_count = data.get("total_count", 0)
                    offset = data.get("offset", 0)
                    GLib.idle_add(
                        self._append_items_to_listbox,
                        items,
                        total_count,
                        offset,
                        "pasted",
                    )

        except Exception as e:
            print(f"WebSocket error fetching more {list_type} items: {e}")
            traceback.print_exc()
            GLib.idle_add(
                lambda: print(f"Error loading more items: {str(e)}") or False
            )
        finally:
            if list_type == "copied":
                GLib.idle_add(lambda: self.copied_loader.set_visible(False))
                self.copied_loading = False
            else:
                GLib.idle_add(lambda: self.pasted_loader.set_visible(False))
                self.pasted_loading = False

    def _append_items_to_listbox(self, items, total_count, offset, list_type):
        """Append new items to the respective listbox"""
        if list_type == "copied":
            listbox = self.copied_listbox
            self.copied_offset = offset
            self.copied_total = total_count
            self.copied_has_more = (
                self.copied_offset + len(items)
            ) < self.copied_total
            self.copied_loader.set_visible(False)
            self.copied_loading = False
        else:  # pasted
            listbox = self.pasted_listbox
            self.pasted_offset = offset
            self.pasted_total = total_count
            self.pasted_has_more = (
                self.pasted_offset + len(items)
            ) < self.pasted_total
            self.pasted_loader.set_visible(False)
            self.pasted_loading = False

        for item in items:
            row = ClipboardItemRow(
                item,
                self,
                show_pasted_time=(list_type == "pasted"),
                search_query=self.search_query,
            )
            listbox.append(row)

        # Count current rows in listbox
        current_count = 0
        index = 0
        while True:
            row = listbox.get_row_at_index(index)
            if row is None:
                break
            current_count += 1
            index += 1

        # Update status label
        if list_type == "copied":
            self.copied_status_label.set_label(
                f"Showing {current_count} of {self.copied_total} items"
            )
        else:
            self.pasted_status_label.set_label(
                f"Showing {current_count} of {self.pasted_total} items"
            )

        return False  # Don't repeat

    def _show_splash_screen(self, button):
        """Show the about dialog"""
        about = AboutWindow()
        about.set_transient_for(self)
        about.set_modal(True)
        about.show()

    def _show_settings_page(self, button):
        self.main_stack.set_visible_child_name("settings")
        self.title_stack.set_visible_child_name("settings")
        self.button_stack.set_visible_child_name("settings")
        # Hide tab bar, filter bar, and search when in settings
        self.tab_bar.set_visible(False)
        self.filter_bar.set_visible(False)
        self.search_container.set_visible(False)

    def _show_tabs_page(self, button):
        self.main_stack.set_visible_child_name("tabs")
        self.title_stack.set_visible_child_name("main")
        self.button_stack.set_visible_child_name("main")
        # Show tab bar and search when returning to main view
        self.tab_bar.set_visible(True)
        self.search_container.set_visible(True)
        # Filter bar visibility is handled by tab selection logic

    def _create_settings_page(self):
        """Create the settings page"""
        settings_page = Adw.PreferencesPage()

        # Display Settings Group
        display_group = Adw.PreferencesGroup()
        display_group.set_title("Display Settings")
        display_group.set_description(
            "Configure how clipboard items are displayed"
        )

        # Item Width setting
        item_width_row = Adw.SpinRow()
        item_width_row.set_title("Item Width")
        item_width_row.set_subtitle(
            "Width of clipboard item cards in pixels (50-1000)"
        )
        item_width_row.set_adjustment(
            Gtk.Adjustment.new(
                value=self.settings.item_width,
                lower=50,
                upper=1000,
                step_increment=10,
                page_increment=50,
                page_size=0,
            )
        )
        item_width_row.set_digits(0)
        self.item_width_spin = item_width_row
        display_group.add(item_width_row)

        # Item Height setting
        item_height_row = Adw.SpinRow()
        item_height_row.set_title("Item Height")
        item_height_row.set_subtitle(
            "Height of clipboard item cards in pixels (50-1000)"
        )
        item_height_row.set_adjustment(
            Gtk.Adjustment.new(
                value=self.settings.item_height,
                lower=50,
                upper=1000,
                step_increment=10,
                page_increment=50,
                page_size=0,
            )
        )
        item_height_row.set_digits(0)
        self.item_height_spin = item_height_row
        display_group.add(item_height_row)

        # Max Page Length setting
        page_length_row = Adw.SpinRow()
        page_length_row.set_title("Max Page Length")
        page_length_row.set_subtitle(
            "Maximum number of items to load per page (1-100)"
        )
        page_length_row.set_adjustment(
            Gtk.Adjustment.new(
                value=self.settings.max_page_length,
                lower=1,
                upper=100,
                step_increment=1,
                page_increment=10,
                page_size=0,
            )
        )
        page_length_row.set_digits(0)
        self.page_length_spin = page_length_row
        display_group.add(page_length_row)

        settings_page.add(display_group)

        # Storage Settings Group
        storage_group = Adw.PreferencesGroup()
        storage_group.set_title("Storage")
        storage_group.set_description("Database storage information")

        # Database size row
        db_size_row = Adw.ActionRow()
        db_size_row.set_title("Database Size")

        # Calculate database size
        db_path = Path.home() / ".local" / "share" / "tfcbm" / "clipboard.db"
        if db_path.exists():
            size_bytes = os.path.getsize(db_path)
            size_mb = size_bytes / (1024 * 1024)  # Convert to MB
            db_size_row.set_subtitle(f"{size_mb:.2f} MB")
        else:
            db_size_row.set_subtitle("Database not found")

        storage_group.add(db_size_row)
        settings_page.add(storage_group)

        # Actions Group (for Save button)
        actions_group = Adw.PreferencesGroup()
        actions_group.set_title("Actions")

        # Create a button row for saving settings
        save_row = Adw.ActionRow()
        save_row.set_title("Save Settings")
        save_row.set_subtitle("Apply changes and save to settings.yml")

        save_button = Gtk.Button()
        save_button.set_label("Apply & Save")
        save_button.add_css_class("suggested-action")
        save_button.set_valign(Gtk.Align.CENTER)
        save_button.connect("clicked", self._on_save_settings)
        save_row.add_suffix(save_button)

        actions_group.add(save_row)
        settings_page.add(actions_group)

        return settings_page

    def _on_save_settings(self, button):
        """Save settings changes to YAML file and apply them"""
        try:
            # Get values from spin rows
            new_item_width = int(self.item_width_spin.get_value())
            new_item_height = int(self.item_height_spin.get_value())
            new_page_length = int(self.page_length_spin.get_value())

            # Prepare settings update dictionary
            settings_update = {
                "display.item_width": new_item_width,
                "display.item_height": new_item_height,
                "display.max_page_length": new_page_length,
            }

            # Update settings using the settings manager
            self.settings.update_settings(**settings_update)

            # Print message
            self.show_notification(
                "Settings saved successfully! Restart the app to apply changes."
            )

            print(
                f"Settings saved: item_width={new_item_width}, item_height={new_item_height}, max_page_length={new_page_length}"
            )

        except Exception as e:
            # Print message
            self.show_notification(f"Error saving settings: {str(e)}")
            print(f"Error saving settings: {e}")

    def _on_close_request(self, window):
        """Handle window close request - kill server before exiting"""
        if self.server_pid:
            try:

                print(f"\nKilling server (PID: {self.server_pid})...")
                os.kill(self.server_pid, signal.SIGTERM)

                # Also kill the tee process if it exists

                subprocess.run(
                    ["pkill", "-P", str(self.server_pid)],
                    stderr=subprocess.DEVNULL,
                )
            except Exception as e:
                print(f"Error killing server: {e}")

        print("Exiting UI...")
        return False  # Allow window to close

    def _on_focus_changed(self, window, param):
        """Handle window focus changes - clear secret authentication when focus is lost."""
        if not self.is_active():
            # Window lost focus or was minimized - clear secret authentication
            logger.info("Window focus lost, clearing secret authentication")
            self.password_service.clear_authentication()

    def _create_filter_bar(self):
        """Create the filter bar with system content types, file extensions, and controls"""
        # Store active filters
        self.active_filters = set()
        self.file_extensions = []
        self.system_filters_visible = True  # Start expanded

        # Main filter bar container
        self.filter_bar = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=6
        )
        self.filter_bar.set_margin_top(6)
        self.filter_bar.set_margin_bottom(6)
        self.filter_bar.set_margin_start(8)
        self.filter_bar.set_margin_end(8)
        self.filter_bar.add_css_class("toolbar")
        self.filter_bar.set_visible(True)  # Ensure it's visible

        # Filter toggle button (to show/hide system filters)
        self.filter_toggle_btn = Gtk.ToggleButton()
        # Try multiple icon names as fallback
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
                print(f"[DEBUG] Using icon: {icon_name}", flush=True)
                icon_found = True
                break

        # If no icon found, use text label as fallback
        if not icon_found:
            self.filter_toggle_btn.set_label("⚙")
            print(
                "[DEBUG] No icon found, using text label fallback", flush=True
            )

        self.filter_toggle_btn.set_tooltip_text("Show/hide system filters")
        self.filter_toggle_btn.add_css_class("flat")
        self.filter_toggle_btn.set_size_request(
            32, 32
        )  # Give it explicit size
        self.filter_toggle_btn.set_visible(True)  # Ensure visible
        self.filter_toggle_btn.set_sensitive(True)  # Ensure enabled
        # self.filter_bar.append(self.filter_toggle_btn)

        print(
            "[DEBUG] Filter toggle button created and added to filter bar",
            flush=True,
        )

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

        # Clear filters button
        clear_btn = Gtk.Button()
        clear_btn.set_icon_name("edit-clear-symbolic")
        clear_btn.set_tooltip_text("Clear all filters")
        clear_btn.add_css_class("flat")
        clear_btn.connect("clicked", self._on_clear_filters)
        self.filter_bar.append(clear_btn)

        # Separator
        separator = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        self.filter_bar.append(separator)

        # Sort toggle button (for current tab)
        self.filter_sort_btn = Gtk.Button()
        self.filter_sort_btn.set_icon_name("view-sort-descending-symbolic")
        self.filter_sort_btn.set_tooltip_text("Newest first ↓")
        self.filter_sort_btn.add_css_class("flat")
        self.filter_sort_btn.add_css_class("sort-toggle")
        self.filter_sort_btn.connect(
            "clicked", lambda btn: self._toggle_sort_from_toolbar()
        )
        self.filter_bar.append(self.filter_sort_btn)

        # Jump to top button (for current tab)
        jump_btn = Gtk.Button()
        jump_btn.set_icon_name("go-top-symbolic")
        jump_btn.set_tooltip_text("Jump to top")
        jump_btn.add_css_class("flat")
        jump_btn.connect(
            "clicked", lambda btn: self._jump_to_top_from_toolbar()
        )
        self.filter_bar.append(jump_btn)

        # Add system content type filters (initially hidden)
        self._add_system_filters()

        # Load file extensions - DISABLED to only show basic filters
        # self._load_file_extensions()

    def _add_system_filters(self):
        """Add system content type filter buttons"""
        self.system_filter_chips = []  # Track system filter chips
        system_filters = [
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
        self, filter_id, label, icon_name=None, is_system=False
    ):
        """Create a small filter chip button"""
        chip = Gtk.ToggleButton()
        chip.set_has_frame(False)
        chip.add_css_class("pill")

        chip_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)

        if icon_name:
            icon = Gtk.Image.new_from_icon_name(icon_name)
            icon.set_pixel_size(12)
            chip_box.append(icon)

        chip_label = Gtk.Label(label=label)
        chip_label.add_css_class("caption")
        chip_box.append(chip_label)

        chip.set_child(chip_box)
        chip.connect(
            "toggled", lambda btn: self._on_filter_toggled(filter_id, btn)
        )

        # Wrap in FlowBoxChild
        flow_child = Gtk.FlowBoxChild()
        flow_child.set_child(chip)

        # Hide system filters initially
        if is_system:
            flow_child.set_visible(True)

        self.filter_box.append(flow_child)

        return flow_child

    def _load_file_extensions(self):
        """Load available file extensions from server"""

        async def fetch_extensions():
            try:
                uri = "ws://localhost:8765"
                async with websockets.connect(
                    uri, max_size=5 * 1024 * 1024
                ) as websocket:
                    request = {"action": "get_file_extensions"}
                    await websocket.send(json.dumps(request))

                    response = await websocket.recv()
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

    def _get_icon_for_extension(self, extension):
        """Get appropriate icon for file extension"""
        # Map common extensions to icons
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

    def _on_filter_toggled(self, filter_id, button):
        """Handle filter chip toggle"""
        if button.get_active():
            self.active_filters.add(filter_id)
        else:
            self.active_filters.discard(filter_id)

        print(
            f"[FILTER] Toggled filter '{filter_id}', active: {button.get_active()}"
        )
        print(f"[FILTER] Current active filters: {self.active_filters}")

        # Apply filters
        self._apply_filters()

    def _on_clear_filters(self, button):
        """Clear all active filters"""
        self.active_filters.clear()

        # Uncheck all filter chips
        for flow_child in list(self.filter_box):
            chip = flow_child.get_child()
            if isinstance(chip, Gtk.ToggleButton):
                chip.set_active(False)

        # Reload items
        self._apply_filters()

    def _apply_filters(self):
        """Apply active filters to the item list - reload from DB with filters"""
        # Always reload from database when filters change
        # This ensures we get a fresh set of items matching the current filters
        # and can load more filtered items when scrolling
        self._reload_current_tab()

    def _reload_current_tab(self):
        """Reload items in the current tab"""
        current_page = self.tab_view.get_selected_page()
        if not current_page:
            return

        is_copied_tab = current_page.get_title() == "Recently Copied"
        if is_copied_tab:
            # Clear and reload copied items
            for row in list(self.copied_listbox):
                self.copied_listbox.remove(row)
            self.current_page = 0
            self.has_more_copied = True
            self.load_history()
        else:
            # Clear and reload pasted items
            for row in list(self.pasted_listbox):
                self.pasted_listbox.remove(row)
            self.current_pasted_page = 0
            self.has_more_pasted = True
            self.load_pasted_history()

    def _on_close_page(self, tab_view, page):
        """Prevent pages from being closed. This should also hide the close button."""
        logger.info("Intercepted 'close-page' signal. Preventing tab closure.")
        return True  # Returning True handles the signal and prevents the default action (closing)

    def _on_search_changed(self, entry):
        """Handle search entry text changes with 200ms debouncing"""
        # Cancel existing timer if any
        if self.search_timer:
            GLib.source_remove(self.search_timer)
            self.search_timer = None

        query = entry.get_text().strip()

        # If query is empty, clear search and restore normal view
        if not query:
            self.search_query = ""
            self.search_active = False
            self.search_results = []
            self._restore_normal_view()
            return

        # Set up 200ms delay before searching (snappy but still debounced)
        self.search_timer = GLib.timeout_add(200, self._perform_search, query)

    def _on_search_activate(self, entry):
        """Handle Enter key press - search immediately"""
        # Cancel debounce timer
        if self.search_timer:
            GLib.source_remove(self.search_timer)
            self.search_timer = None

        query = entry.get_text().strip()
        if query:
            self._perform_search(query)

    def _perform_search(self, query):
        """Perform the actual search via WebSocket"""
        self.search_query = query
        self.search_timer = None  # Clear timer reference

        print(f"[UI] Searching for: '{query}'")

        def run_search():
            try:

                async def search():
                    uri = "ws://localhost:8765"
                    max_size = 5 * 1024 * 1024  # 5MB
                    async with websockets.connect(
                        uri, max_size=max_size
                    ) as websocket:
                        request = {
                            "action": "search",
                            "query": query,
                            "limit": 100,
                        }
                        # Feature 2: Include active filters in search request
                        if self.active_filters:
                            request["filters"] = list(self.active_filters)
                            print(
                                f"[UI] Searching with filters: {list(self.active_filters)}"
                            )
                        await websocket.send(json.dumps(request))

                        response = await websocket.recv()
                        data = json.loads(response)

                        if data.get("type") == "search_results":
                            items = data.get("items", [])
                            result_count = data.get("count", 0)
                            print(f"[UI] Search results: {result_count} items")
                            GLib.idle_add(
                                self._display_search_results, items, query
                            )

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(search())
                finally:
                    loop.close()
            except Exception as e:
                print(f"[UI] Search error: {e}")
                traceback.print_exc()
                GLib.idle_add(
                    lambda: self.show_notification(f"Search error: {str(e)}")
                    or False
                )

        threading.Thread(target=run_search, daemon=True).start()
        return False  # Don't repeat timer

    def _display_search_results(self, items, query):
        """Display search results in the current tab"""
        self.search_active = True
        self.search_results = items

        # Determine which listbox to update based on current tab
        if self.current_tab == "pasted":
            listbox = self.pasted_listbox
            status_label = self.pasted_status_label
            show_pasted_time = True
        else:  # copied
            listbox = self.copied_listbox
            status_label = self.copied_status_label
            show_pasted_time = False

        # Clear existing items
        while True:
            row = listbox.get_row_at_index(0)
            if row is None:
                break
            listbox.remove(row)

        # Display search results or empty message
        if items:
            for item in items:
                row = ClipboardItemRow(
                    item,
                    self,
                    show_pasted_time=show_pasted_time,
                    search_query=self.search_query,
                )
                listbox.append(row)
            status_label.set_label(
                f"Search: {len(items)} results for '{query}'"
            )
        else:
            # Show empty results message
            empty_box = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=12
            )
            empty_box.set_valign(Gtk.Align.CENTER)
            empty_box.set_margin_top(60)
            empty_box.set_margin_bottom(60)

            empty_label = Gtk.Label(label="No results found")
            empty_label.add_css_class("title-2")
            empty_box.append(empty_label)

            hint_label = Gtk.Label(label=f"No clipboard items match '{query}'")
            hint_label.add_css_class("dim-label")
            empty_box.append(hint_label)

            listbox.append(empty_box)
            status_label.set_label(f"Search: 0 results for '{query}'")

        listbox.queue_draw()
        # Scroll to top to ensure results are visible
        self._jump_to_top(self.current_tab)

        return False

    def _restore_normal_view(self):
        """Restore normal view when search is cleared"""
        # Reset pagination and reload current tab
        if self.current_tab == "pasted":
            self.pasted_offset = 0
            self.pasted_has_more = True
            GLib.idle_add(self.load_pasted_history)
        else:  # copied
            # Reload first page of copied items
            def reload_copied():
                try:

                    async def get_history():
                        uri = "ws://localhost:8765"
                        max_size = 5 * 1024 * 1024
                        async with websockets.connect(
                            uri, max_size=max_size
                        ) as websocket:
                            request = {
                                "action": "get_history",
                                "limit": self.page_size,
                            }
                            if self.active_filters:
                                request["filters"] = list(self.active_filters)
                            await websocket.send(json.dumps(request))
                            response = await websocket.recv()
                            data = json.loads(response)

                            if data.get("type") == "history":
                                items = data.get("items", [])
                                total_count = data.get("total_count", 0)
                                offset = data.get("offset", 0)
                                GLib.idle_add(
                                    self._initial_history_load,
                                    items,
                                    total_count,
                                    offset,
                                )

                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(get_history())
                    finally:
                        loop.close()
                except Exception as e:
                    print(f"[UI] Error reloading history: {e}")

            threading.Thread(target=reload_copied, daemon=True).start()

    # ========== Tag Methods ==========

    def load_tags(self):
        """Load tags from server via WebSocket"""
        self.tags_load_start_time = time.time()
        logger.info("Starting tags load...")

        def run_load():
            try:

                async def fetch_tags():
                    uri = "ws://localhost:8765"
                    async with websockets.connect(uri) as websocket:
                        request = {"action": "get_tags"}
                        await websocket.send(json.dumps(request))

                        response = await websocket.recv()
                        data = json.loads(response)

                        if data.get("type") == "tags":
                            tags = data.get("tags", [])
                            # Add system tags based on item types
                            system_tags = [
                                {
                                    "id": "system_text",
                                    "name": "Text",
                                    "color": "#3584e4",
                                    "is_system": True,
                                },
                                {
                                    "id": "system_image",
                                    "name": "Image",
                                    "color": "#33d17a",
                                    "is_system": True,
                                },
                                {
                                    "id": "system_screenshot",
                                    "name": "Screenshot",
                                    "color": "#e01b24",
                                    "is_system": True,
                                },
                                {
                                    "id": "system_url",
                                    "name": "URL",
                                    "color": "#c061cb",
                                    "is_system": True,
                                },
                            ]
                            all_tags = system_tags + tags
                            GLib.idle_add(self._update_tags, all_tags)

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(fetch_tags())
                finally:
                    loop.close()
            except Exception as e:
                print(f"[UI] Error loading tags: {e}")

        threading.Thread(target=run_load, daemon=True).start()

    def _update_tags(self, tags):
        """Update tags in UI thread"""
        if hasattr(self, "tags_load_start_time"):
            duration = time.time() - self.tags_load_start_time
            logger.info(f"Tags loaded in {duration:.2f} seconds")
            del self.tags_load_start_time
        self.all_tags = tags
        self._refresh_tag_display()

    def _refresh_tag_display(self):
        """Refresh the tag display area"""
        # Clear existing tags
        while True:
            child = self.tag_flowbox.get_first_child()
            if not child:
                break
            self.tag_flowbox.remove(child)

        self.tag_buttons = {}

        # Filter out system tags - only show custom user tags
        user_tags = [
            tag for tag in self.all_tags if not tag.get("is_system", False)
        ]

        # Add tag buttons
        for tag in user_tags:
            tag_id = tag.get("id")
            tag_name = tag.get("name", "")
            tag_color = tag.get("color", "#9a9996")
            is_selected = tag_id in self.selected_tag_ids

            # Create button for tag
            btn = Gtk.Button.new_with_label(tag_name)
            btn.add_css_class("pill")

            # Apply color styling - selected tags colored, unselected greyed out
            css_provider = Gtk.CssProvider()
            if is_selected:
                css_data = f"button.pill {{ background-color: alpha({tag_color}, 0.25); color: {tag_color}; font-size: 9pt; font-weight: normal; padding: 2px 8px; min-height: 20px; border: 1px solid alpha({tag_color}, 0.4); border-radius: 2px; }}"
            else:
                # Unselected: greyed out
                css_data = "button.pill { background-color: alpha(#666666, 0.08); color: alpha(#666666, 0.5); font-size: 9pt; font-weight: normal; padding: 2px 8px; min-height: 20px; border: 1px solid alpha(#666666, 0.2); border-radius: 2px; }"
            css_provider.load_from_data(css_data.encode())
            btn.get_style_context().add_provider(
                css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

            # Add drag source for drag-and-drop
            drag_source = Gtk.DragSource.new()
            drag_source.set_actions(Gdk.DragAction.COPY)
            drag_source.connect("prepare", self._on_tag_drag_prepare, tag)
            drag_source.connect("drag-begin", self._on_tag_drag_begin)
            btn.add_controller(drag_source)

            btn.connect(
                "clicked", lambda b, tid=tag_id: self._on_tag_clicked(tid)
            )

            self.tag_buttons[tag_id] = btn
            self.tag_flowbox.append(btn)

    def _on_tag_clicked(self, tag_id):
        """Handle tag button click - toggle selection"""
        if tag_id in self.selected_tag_ids:
            self.selected_tag_ids.remove(tag_id)
        else:
            self.selected_tag_ids.append(tag_id)

        # Refresh display to update button styles
        self._refresh_tag_display()

        # Apply filter if tags are selected
        if self.selected_tag_ids:
            self._apply_tag_filter()
        else:
            self._restore_filtered_view()

    def _clear_tag_filter(self):
        """Clear all tag filters"""
        self.selected_tag_ids = []
        self._refresh_tag_display()
        self._restore_filtered_view()

    def _apply_tag_filter(self):
        """Filter items by selected tags at UI level (no DB calls)"""
        print(f"[UI] Applying tag filter: {self.selected_tag_ids}")

        if not self.selected_tag_ids:
            self._restore_normal_view()
            return

        # Map system tag IDs to item types
        type_map = {
            "system_text": ["text"],
            "system_image": [
                "image/generic",
                "image/file",
                "image/web",
                "image/screenshot",
            ],
            "system_screenshot": ["image/screenshot"],
            "system_url": ["url"],
        }

        # Get user-defined tag IDs (non-system tags) - convert to string to check
        user_tag_ids = [
            tag_id
            for tag_id in self.selected_tag_ids
            if not str(tag_id).startswith("system_")
        ]

        # Get allowed types from system tags
        allowed_types = []
        for tag_id in self.selected_tag_ids:
            if tag_id in type_map:
                allowed_types.extend(type_map[tag_id])

        # Determine which listbox to update
        if self.current_tab == "pasted":
            listbox = self.pasted_listbox
        else:
            listbox = self.copied_listbox

        # Filter rows by showing/hiding them based on tags
        visible_count = 0
        i = 0
        while True:
            row = listbox.get_row_at_index(i)
            if not row:
                break

            if hasattr(row, "item"):
                item = row.item
                item_type = item.get("type", "")
                item_tags = item.get("tags", [])

                # Extract tag IDs from item tags
                item_tag_ids = [
                    tag.get("id") for tag in item_tags if isinstance(tag, dict)
                ]

                # Check if item matches filter
                matches = False

                # If we have system tag filters, check type match
                if allowed_types:
                    if item_type in allowed_types:
                        # If we also have user tags, check if item has those tags
                        if user_tag_ids:
                            # Item must have at least one of the selected user tags
                            if any(
                                tag_id in item_tag_ids
                                for tag_id in user_tag_ids
                            ):
                                matches = True
                        else:
                            # No user tags, just type match is enough
                            matches = True

                # If we only have user tag filters (no system tags)
                elif user_tag_ids:
                    if any(tag_id in item_tag_ids for tag_id in user_tag_ids):
                        matches = True

                # Show/hide row based on match
                row.set_visible(matches)
                if matches:
                    visible_count += 1

            i += 1

        self.filter_active = True
        self.show_notification(f"Showing {visible_count} filtered items")

    def _restore_filtered_view(self):
        """Restore normal unfiltered view by making all rows visible"""
        if not self.filter_active:
            return

        self.filter_active = False

        # Determine which listbox to update
        if self.current_tab == "pasted":
            listbox = self.pasted_listbox
        else:
            listbox = self.copied_listbox

        # Show all rows again
        i = 0
        while True:
            row = listbox.get_row_at_index(i)
            if not row:
                break
            row.set_visible(True)
            i += 1

    # ========== Tag Manager Methods ==========

    def load_user_tags(self):
        """Load user-defined tags for the tag manager"""
        self.user_tags_load_start_time = time.time()
        logger.info("Starting user tags load...")

        def run_load():
            try:

                async def fetch_tags():
                    uri = "ws://localhost:8765"
                    async with websockets.connect(uri) as websocket:
                        request = {"action": "get_tags"}
                        await websocket.send(json.dumps(request))

                        response = await websocket.recv()
                        data = json.loads(response)

                        if data.get("type") == "tags":
                            all_tags = data.get("tags", [])
                            # Only user-defined tags (filter out system tags)
                            user_tags = [
                                tag
                                for tag in all_tags
                                if not tag.get("is_system", False)
                            ]
                            GLib.idle_add(
                                self._refresh_user_tags_display, user_tags
                            )

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(fetch_tags())
                finally:
                    loop.close()
            except Exception as e:
                print(f"[UI] Error loading user tags: {e}")

        threading.Thread(target=run_load, daemon=True).start()

    def _on_tag_drag_prepare(self, drag_source, x, y, tag):
        """Prepare data for tag drag operation"""
        self.dragged_tag = tag
        # We'll pass the tag ID as a string
        tag_id = str(tag.get("id"))
        value = GObject.Value(str, tag_id)
        return Gdk.ContentProvider.new_for_value(value)

    def _on_tag_drag_begin(self, drag_source, drag):
        """Called when tag drag begins - set drag icon"""
        widget = drag_source.get_widget()
        drag_source.set_icon(Gtk.WidgetPaintable.new(widget), 0, 0)

    def _on_tag_dropped_on_item(self, tag_id, item_id):
        """Handle tag drop on an item"""
        print(f"[UI] Tag {tag_id} dropped on item {item_id}")

        def run_add_tag():
            try:

                async def add_tag():
                    uri = "ws://localhost:8765"
                    async with websockets.connect(uri) as websocket:
                        request = {
                            "action": "add_item_tag",
                            "item_id": item_id,
                            "tag_id": int(tag_id),
                        }
                        await websocket.send(json.dumps(request))
                        response = await websocket.recv()
                        data = json.loads(response)

                        if data.get("success"):
                            print(
                                f"[UI] Successfully added tag {tag_id} to item {item_id}"
                            )
                            # Find the row and reload its tags
                            for row in self.copied_listbox:
                                if row.item.get("id") == item_id:
                                    row._load_item_tags()
                                    break
                            for row in self.pasted_listbox:
                                if row.item.get("id") == item_id:
                                    row._load_item_tags()
                                    break
                        else:
                            print(
                                f"[UI] Failed to add tag: {data.get('error', 'Unknown error')}"
                            )

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(add_tag())
                finally:
                    loop.close()
            except Exception as e:
                print(f"[UI] Error adding tag: {e}")

        threading.Thread(target=run_add_tag, daemon=True).start()

    def _refresh_user_tags_display(self, tags):
        """Refresh the user tags display in the tag manager"""
        if hasattr(self, "user_tags_load_start_time"):
            duration = time.time() - self.user_tags_load_start_time
            logger.info(f"User tags loaded in {duration:.2f} seconds")
            del self.user_tags_load_start_time
        # Clear existing tags - AdwPreferencesGroup stores rows internally
        # We need to track and remove only the rows we added
        if hasattr(self, "_user_tag_rows"):
            for row in self._user_tag_rows:
                self.user_tags_group.remove(row)

        self._user_tag_rows = []

        # Add tag rows
        if not tags:
            empty_row = Adw.ActionRow()
            empty_row.set_title("No custom tags yet")
            empty_row.set_subtitle(
                "Create your first tag to organize clipboard items"
            )
            self.user_tags_group.add(empty_row)
            self._user_tag_rows.append(empty_row)
        else:
            for tag in tags:
                tag_id = tag.get("id")
                tag_name = tag.get("name", "")
                tag_color = tag.get("color", "#9a9996")

                tag_row = Adw.ActionRow()
                tag_row.set_title(tag_name)

                # Create a color indicator box
                color_box = Gtk.Box()
                color_box.set_size_request(20, 20)
                color_box.add_css_class("card")

                # Apply color
                css_provider = Gtk.CssProvider()
                css_data = f"box {{ background-color: {tag_color}; border-radius: 4px; }}"
                css_provider.load_from_data(css_data.encode())
                color_box.get_style_context().add_provider(
                    css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                )
                tag_row.add_prefix(color_box)

                # Edit button
                edit_button = Gtk.Button()
                edit_button.set_icon_name("document-edit-symbolic")
                edit_button.set_valign(Gtk.Align.CENTER)
                edit_button.add_css_class("flat")
                edit_button.connect(
                    "clicked", lambda b, tid=tag_id: self._on_edit_tag(tid)
                )
                tag_row.add_suffix(edit_button)

                # Delete button
                delete_button = Gtk.Button()
                delete_button.set_icon_name("user-trash-symbolic")
                delete_button.set_valign(Gtk.Align.CENTER)
                delete_button.add_css_class("flat")
                delete_button.add_css_class("destructive-action")
                delete_button.connect(
                    "clicked", lambda b, tid=tag_id: self._on_delete_tag(tid)
                )
                tag_row.add_suffix(delete_button)

                # Add drag source for drag-and-drop
                drag_source = Gtk.DragSource.new()
                drag_source.set_actions(Gdk.DragAction.COPY)
                drag_source.connect("prepare", self._on_tag_drag_prepare, tag)
                drag_source.connect("drag-begin", self._on_tag_drag_begin)
                tag_row.add_controller(drag_source)

                self.user_tags_group.add(tag_row)
                self._user_tag_rows.append(tag_row)

    def _on_create_tag(self, button):
        """Show dialog to create a new tag"""
        dialog = Adw.MessageDialog.new(self)
        dialog.set_heading("Create New Tag")
        dialog.set_body("Enter a name for the new tag")

        # Create entry for tag name
        entry_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        entry_box.set_margin_top(12)
        entry_box.set_margin_bottom(12)
        entry_box.set_margin_start(12)
        entry_box.set_margin_end(12)

        name_entry = Gtk.Entry()
        name_entry.set_placeholder_text("Tag name")
        entry_box.append(name_entry)

        # Color picker - use a simple dropdown with predefined colors
        color_label = Gtk.Label()
        color_label.set_text("Choose a color:")
        color_label.set_halign(Gtk.Align.START)
        entry_box.append(color_label)

        color_flow = Gtk.FlowBox()
        color_flow.set_selection_mode(Gtk.SelectionMode.SINGLE)
        color_flow.set_max_children_per_line(6)
        color_flow.set_column_spacing(6)
        color_flow.set_row_spacing(6)

        colors = [
            "#3584e4",
            "#33d17a",
            "#f6d32d",
            "#ff7800",
            "#e01b24",
            "#9141ac",
            "#986a44",
            "#5e5c64",
        ]
        for color in colors:
            color_btn = Gtk.Button()
            color_btn.set_size_request(40, 40)
            # Store color value on button for later retrieval
            color_btn.color_value = color
            css_provider = Gtk.CssProvider()
            css_data = (
                f"button {{ background-color: {color}; border-radius: 20px; }}"
            )
            css_provider.load_from_data(css_data.encode())
            color_btn.get_style_context().add_provider(
                css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

            # Make button clickable to select its flowbox child
            def on_color_click(btn, flow=color_flow):
                # Find and select this button's parent FlowBoxChild
                parent = btn.get_parent()
                if parent:
                    flow.select_child(parent)

            color_btn.connect("clicked", on_color_click)
            color_flow.append(color_btn)

        color_flow.select_child(color_flow.get_child_at_index(0))
        entry_box.append(color_flow)

        dialog.set_extra_child(entry_box)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("create", "Create")
        dialog.set_response_appearance(
            "create", Adw.ResponseAppearance.SUGGESTED
        )

        def on_response(dialog, response):
            if response == "create":
                tag_name = name_entry.get_text().strip()
                if not tag_name:
                    print("Tag name cannot be empty")
                    return

                # Get selected color from the selected FlowBoxChild's button
                selected = color_flow.get_selected_children()
                if selected and len(selected) > 0:
                    # Get the button from the FlowBoxChild
                    flow_child = selected[0]
                    button = flow_child.get_child()
                    if hasattr(button, "color_value"):
                        selected_color = button.color_value
                    else:
                        selected_color = colors[0]
                else:
                    selected_color = colors[0]

                # Create tag via WebSocket
                self._create_tag_on_server(tag_name, selected_color)

        dialog.connect("response", on_response)
        dialog.present()

    def _create_tag_on_server(self, name, color):
        """Create a new tag on the server"""

        def run_create():
            try:

                async def create_tag():
                    print(f"[UI] Creating tag: name='{name}', color='{color}'")
                    uri = "ws://localhost:8765"
                    async with websockets.connect(uri) as websocket:
                        request = {
                            "action": "create_tag",
                            "name": name,
                            "color": color,
                        }
                        print(f"[UI] Sending create_tag request: {request}")
                        await websocket.send(json.dumps(request))

                        response = await websocket.recv()
                        data = json.loads(response)
                        print(f"[UI] Received response: {data}")

                        if data.get("type") == "tag_created":
                            print(f"[UI] Tag created successfully")
                            GLib.idle_add(
                                self.show_notification, f"Tag '{name}' created"
                            )
                            GLib.idle_add(self.load_user_tags)
                            GLib.idle_add(
                                self.load_tags
                            )  # Refresh tag filter display
                        else:
                            print(
                                f"[UI] Tag creation failed - unexpected response type: {data.get('type')}"
                            )
                            GLib.idle_add(
                                self.show_notification,
                                f"Failed to create tag: {data.get('message', 'Unknown error')}",
                            )

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(create_tag())
                finally:
                    loop.close()
            except Exception as e:
                print(f"[UI] Exception creating tag: {e}")
                traceback.print_exc()
                GLib.idle_add(
                    self.show_notification, f"Error creating tag: {e}"
                )

        threading.Thread(target=run_create, daemon=True).start()

    def _on_edit_tag(self, tag_id):
        """Show dialog to edit a tag"""
        # Find the tag
        tag = None
        for t in self.all_tags:
            if t.get("id") == tag_id and not t.get("is_system"):
                tag = t
                break

        if not tag:
            self.show_notification("Tag not found")
            return

        dialog = Adw.MessageDialog.new(self)
        dialog.set_heading("Edit Tag")
        dialog.set_body(f"Modify the tag '{tag.get('name')}'")

        # Create entry for tag name
        entry_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        entry_box.set_margin_top(12)
        entry_box.set_margin_bottom(12)
        entry_box.set_margin_start(12)
        entry_box.set_margin_end(12)

        name_entry = Gtk.Entry()
        name_entry.set_text(tag.get("name", ""))
        entry_box.append(name_entry)

        # Color picker
        color_label = Gtk.Label()
        color_label.set_text("Choose a color:")
        color_label.set_halign(Gtk.Align.START)
        entry_box.append(color_label)

        color_flow = Gtk.FlowBox()
        color_flow.set_selection_mode(Gtk.SelectionMode.SINGLE)
        color_flow.set_max_children_per_line(6)
        color_flow.set_column_spacing(6)
        color_flow.set_row_spacing(6)

        colors = [
            "#3584e4",
            "#33d17a",
            "#f6d32d",
            "#ff7800",
            "#e01b24",
            "#9141ac",
            "#986a44",
            "#5e5c64",
        ]
        current_color_index = 0
        if tag.get("color") in colors:
            current_color_index = colors.index(tag.get("color"))

        for color in colors:
            color_btn = Gtk.Button()
            color_btn.set_size_request(40, 40)
            # Store color value on button
            color_btn.color_value = color
            css_provider = Gtk.CssProvider()
            css_data = (
                f"button {{ background-color: {color}; border-radius: 20px; }}"
            )
            css_provider.load_from_data(css_data.encode())
            color_btn.get_style_context().add_provider(
                css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

            # Make button clickable to select its flowbox child
            def on_color_click(btn, flow=color_flow):
                parent = btn.get_parent()
                if parent:
                    flow.select_child(parent)

            color_btn.connect("clicked", on_color_click)
            color_flow.append(color_btn)

        color_flow.select_child(
            color_flow.get_child_at_index(current_color_index)
        )
        entry_box.append(color_flow)

        dialog.set_extra_child(entry_box)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("save", "Save")
        dialog.set_response_appearance(
            "save", Adw.ResponseAppearance.SUGGESTED
        )

        def on_response(dialog, response):
            if response == "save":
                tag_name = name_entry.get_text().strip()
                if not tag_name:
                    print("Tag name cannot be empty")
                    return

                # Get selected color from the selected FlowBoxChild's button
                selected = color_flow.get_selected_children()
                if selected and len(selected) > 0:
                    flow_child = selected[0]
                    button = flow_child.get_child()
                    if hasattr(button, "color_value"):
                        selected_color = button.color_value
                    else:
                        selected_color = colors[current_color_index]
                else:
                    selected_color = colors[current_color_index]

                # Update tag via WebSocket
                self._update_tag_on_server(tag_id, tag_name, selected_color)

        dialog.connect("response", on_response)
        dialog.present()

    def _update_tag_on_server(self, tag_id, name, color):
        """Update a tag on the server"""

        def run_update():
            try:

                async def update_tag():
                    uri = "ws://localhost:8765"
                    async with websockets.connect(uri) as websocket:
                        request = {
                            "action": "update_tag",
                            "tag_id": tag_id,
                            "name": name,
                            "color": color,
                        }
                        await websocket.send(json.dumps(request))

                        response = await websocket.recv()
                        data = json.loads(response)

                        if data.get("type") == "tag_updated":
                            GLib.idle_add(
                                self.show_notification, f"Tag updated"
                            )
                            GLib.idle_add(self.load_user_tags)
                            GLib.idle_add(
                                self.load_tags
                            )  # Refresh tag filter display
                        else:
                            GLib.idle_add(
                                self.show_notification, "Failed to update tag"
                            )

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(update_tag())
                finally:
                    loop.close()
            except Exception as e:
                print(f"[UI] Error updating tag: {e}")
                GLib.idle_add(
                    self.show_notification, f"Error updating tag: {e}"
                )

        threading.Thread(target=run_update, daemon=True).start()

    def _on_delete_tag(self, tag_id):
        """Show confirmation dialog and delete tag"""
        # Find the tag
        tag = None
        for t in self.all_tags:
            if t.get("id") == tag_id:
                tag = t
                break

        if not tag:
            print("Tag not found")
            return

        dialog = Adw.MessageDialog.new(self)
        dialog.set_heading("Delete Tag")
        dialog.set_body(
            f"Are you sure you want to delete the tag '{tag.get('name')}'?"
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("delete", "Delete")
        dialog.set_response_appearance(
            "delete", Adw.ResponseAppearance.DESTRUCTIVE
        )

        def on_response(dialog, response):
            if response == "delete":
                self._delete_tag_on_server(tag_id)

        dialog.connect("response", on_response)
        dialog.present()

    def _delete_tag_on_server(self, tag_id):
        """Delete a tag on the server"""

        def run_delete():
            try:

                async def delete_tag():
                    uri = "ws://localhost:8765"
                    async with websockets.connect(uri) as websocket:
                        request = {"action": "delete_tag", "tag_id": tag_id}
                        await websocket.send(json.dumps(request))

                        response = await websocket.recv()
                        data = json.loads(response)

                        if data.get("type") == "tag_deleted":
                            GLib.idle_add(
                                self.show_notification, "Tag deleted"
                            )
                            GLib.idle_add(self.load_user_tags)
                            GLib.idle_add(
                                self.load_tags
                            )  # Refresh tag filter display
                            GLib.idle_add(
                                self._refresh_all_item_tags
                            )  # Refresh tags on all visible items
                        else:
                            GLib.idle_add(
                                self.show_notification, "Failed to delete tag"
                            )

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(delete_tag())
                finally:
                    loop.close()
            except Exception as e:
                print(f"[UI] Error deleting tag: {e}")
                GLib.idle_add(
                    self.show_notification, f"Error deleting tag: {e}"
                )

        threading.Thread(target=run_delete, daemon=True).start()

    def _refresh_all_item_tags(self):
        """Refresh tag displays on all visible clipboard items."""
        print("[UI] Refreshing tags on all visible items")

        # Refresh tags on all items in copied listbox
        for row in self.copied_listbox:
            if isinstance(row, ClipboardItemRow):
                row._load_item_tags()

        # Refresh tags on all items in pasted listbox
        for row in self.pasted_listbox:
            if isinstance(row, ClipboardItemRow):
                row._load_item_tags()

        print("[UI] Finished refreshing tags on all items")
