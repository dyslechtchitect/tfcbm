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
from ui.managers.filter_bar_manager import FilterBarManager
from ui.managers.keyboard_shortcut_handler import KeyboardShortcutHandler
from ui.managers.notification_manager import NotificationManager
from ui.managers.search_manager import SearchManager
from ui.managers.sort_manager import SortManager
from ui.managers.tab_manager import TabManager
from ui.managers.tag_dialog_manager import TagDialogManager
from ui.managers.tag_filter_manager import TagFilterManager
from ui.managers.user_tags_manager import UserTagsManager
from ui.managers.window_position_manager import WindowPositionManager
from ui.pages.settings_page import SettingsPage
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

        # Initialize WindowPositionManager and position window to the left
        self.position_manager = WindowPositionManager(self)
        self.position_manager.position_left()

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
        self.search_entry.connect("search-changed", self._on_search_changed_wrapper)
        self.search_entry.connect("activate", self._on_search_activate_wrapper)
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

        # Initialize FilterBarManager
        self.filter_bar_manager = FilterBarManager(
            on_filter_changed=self._reload_current_tab
        )

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

        # Create settings page using SettingsPage component
        settings_page_component = SettingsPage(
            settings=self.settings,
            on_save=self._handle_settings_save,
            on_notification=self.show_notification,
        )
        settings_page = settings_page_component.build()
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

        # Initialize UserTagsManager (needs to be after user_tags_group and tag_filter_manager)
        # Will be fully initialized after tag_filter_manager is created

        # Connect tab switch event
        self.tab_view.connect("notify::selected-page", self._on_tab_switched)

        # Add toolbar controls to filter bar
        self.filter_bar_manager.add_toolbar_separator()
        self.filter_sort_btn = self.filter_bar_manager.add_sort_button(
            on_sort_clicked=self._toggle_sort_from_toolbar,
            initial_tooltip="Newest first ↓"
        )
        self.filter_bar_manager.add_jump_to_top_button(
            on_jump_clicked=self._jump_to_top_from_toolbar
        )

        # Add sticky filter bar (contains filters, sort, jump)
        main_box.append(self.filter_bar_manager.build())

        main_box.append(self.main_stack)

        # Add tag filter at the bottom (footer)
        main_box.append(tag_frame)

        # Initialize NotificationManager and add its widget
        self.notification_manager = NotificationManager()
        main_box.append(self.notification_manager.get_widget())

        # Set up main box as content
        self.set_content(main_box)

        # Load clipboard history
        GLib.idle_add(self.load_history)

        # Store current tab state
        self.current_tab = "copied"

        # Initialize SearchManager
        self.search_manager = SearchManager(
            on_display_results=self._display_search_results,
            on_notification=self.show_notification,
        )

        # Initialize SortManager (after filter_sort_btn is created)
        self.sort_manager = SortManager(
            sort_button=self.filter_sort_btn,
            on_history_load=self._initial_history_load,
            on_pasted_load=self._initial_pasted_load,
            get_active_filters=self.filter_bar_manager.get_active_filters,
            page_size=self.page_size,
        )

        # Initialize TabManager
        self.tab_manager = TabManager(
            window_instance=self,
            filter_bar=self.filter_bar_manager.build(),
        )

        # Initialize TagFilterManager
        self.tag_filter_manager = TagFilterManager(
            on_tag_display_refresh=self._refresh_tag_display,
            on_notification=self.show_notification,
        )

        # Initialize UserTagsManager
        self.user_tags_manager = UserTagsManager(
            user_tags_group=self.user_tags_group,
            on_refresh_tag_display=self._refresh_tag_display,
            on_item_tag_reload=self._reload_item_tags,
            window=self,
        )

        # Initialize TagDialogManager
        self.tag_dialog_manager = TagDialogManager(
            parent_window=self,
            on_tag_created=lambda: (
                self.load_user_tags(),
                self.load_tags(),
                self.show_notification("Tag created"),
            ),
            on_tag_updated=lambda: (
                self.load_user_tags(),
                self.load_tags(),
            ),
            get_all_tags=lambda: self.all_tags,
        )

        # Tag state
        self.all_tags = []  # All available tags (system + user)
        self.tag_buttons = {}  # Dict of tag_id -> button widget
        self.filtered_items = []  # Filtered items when tag filter is active
        self.dragged_tag = None

        # Position window to the left (again, to ensure it's positioned)
        self.position_manager.position_left()

        # Set up global keyboard shortcut

        # Load tags for filtering
        self.load_tags()

        # Load user tags for tag manager (via manager)
        self.user_tags_manager.load_user_tags()

        # Initialize KeyboardShortcutHandler
        self.keyboard_handler = KeyboardShortcutHandler(
            self, self.search_entry, self.copied_listbox
        )

        logger.info(
            f"ClipboardWindow initialized in {time.time() - start_time:.2f} seconds"
        )

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
                if self.filter_bar_manager.get_active_filters():
                    request["filters"] = list(self.filter_bar_manager.get_active_filters())
                    print(
                        f"[FILTER] Sending filters to server: {list(self.filter_bar_manager.get_active_filters())}"
                    )
                await websocket.send(json.dumps(request))
                print(
                    f"Requested history with filters: {request.get('filters', 'none')}"
                )

                # Request recently pasted items
                pasted_request = {"action": "get_recently_pasted", "limit": self.page_size}
                if self.filter_bar_manager.get_active_filters():
                    pasted_request["filters"] = list(self.filter_bar_manager.get_active_filters())
                await websocket.send(json.dumps(pasted_request))
                print(
                    f"Requested pasted items with filters: {pasted_request.get('filters', 'none')}"
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
                        if self.filter_bar_manager.get_active_filters():
                            request["filters"] = list(self.filter_bar_manager.get_active_filters())
                            print(
                                f"[FILTER] Requesting pasted items with filters: {list(self.filter_bar_manager.get_active_filters())}"
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
            row = ClipboardItemRow(item, self, search_query=self.search_manager.get_query())
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
                search_query=self.search_manager.get_query(),
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
            row = ClipboardItemRow(item, self, search_query=self.search_manager.get_query())
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
                search_query=self.search_manager.get_query(),
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
        """Show a notification message - delegates to NotificationManager"""
        self.notification_manager.show(message)

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
        """Toggle sort for the currently active tab - delegates to SortManager"""
        # Determine which tab is active
        if self.current_tab == "copied":
            self.sort_manager.toggle_sort("copied")
        else:
            self.sort_manager.toggle_sort("pasted")

    def _jump_to_top_from_toolbar(self):
        """Jump to top for the currently active tab"""
        if self.current_tab == "copied":
            self._jump_to_top("copied")
        else:
            self._jump_to_top("pasted")

    def _on_scroll_changed(self, adjustment, list_type):
        """Handle scroll events for infinite scrolling"""
        # Don't load more items if search is active - search results are complete
        if self.search_manager.is_active():
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
                    if self.filter_bar_manager.get_active_filters():
                        request["filters"] = list(self.filter_bar_manager.get_active_filters())
                else:  # pasted
                    request = {
                        "action": "get_recently_pasted",
                        "offset": self.pasted_offset + self.page_size,
                        "limit": self.page_size,
                    }
                    # Include active filters for pasted items too
                    if self.filter_bar_manager.get_active_filters():
                        request["filters"] = list(self.filter_bar_manager.get_active_filters())

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
                search_query=self.search_manager.get_query(),
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
        self.filter_bar_manager.set_visible(False)
        self.search_container.set_visible(False)

    def _show_tabs_page(self, button):
        self.main_stack.set_visible_child_name("tabs")
        self.title_stack.set_visible_child_name("main")
        self.button_stack.set_visible_child_name("main")
        # Show tab bar and search when returning to main view
        self.tab_bar.set_visible(True)
        self.search_container.set_visible(True)
        # Filter bar visibility is handled by tab selection logic

    def _handle_settings_save(
        self, item_width: int, item_height: int, max_page_length: int
    ) -> None:
        """Handle settings save callback from SettingsPage.

        Args:
            item_width: New item width value
            item_height: New item height value
            max_page_length: New max page length value
        """
        # Prepare settings update dictionary
        settings_update = {
            "display.item_width": item_width,
            "display.item_height": item_height,
            "display.max_page_length": max_page_length,
        }

        # Update settings using the settings manager
        self.settings.update_settings(**settings_update)

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

    def _on_search_changed_wrapper(self, entry):
        """Wrapper for search entry text changes - delegates to SearchManager"""
        result = self.search_manager.on_search_changed(entry, self.filter_bar_manager.get_active_filters)
        if result == "CLEAR":
            self._restore_normal_view()

    def _on_search_activate_wrapper(self, entry):
        """Wrapper for Enter key press - delegates to SearchManager"""
        self.search_manager.on_search_activate(entry, self.filter_bar_manager.get_active_filters)

    def _display_search_results(self, items, query):
        """Display search results in the current tab"""
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
                    search_query=query,
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
                            if self.filter_bar_manager.get_active_filters():
                                request["filters"] = list(self.filter_bar_manager.get_active_filters())
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
            is_selected = tag_id in self.tag_filter_manager.get_selected_tag_ids()

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
        # Toggle tag selection via manager
        self.tag_filter_manager.toggle_tag(tag_id)

        # Apply filter if tags are selected
        if self.tag_filter_manager.get_selected_tag_ids():
            self._apply_tag_filter()
        else:
            self._restore_filtered_view()

    def _clear_tag_filter(self):
        """Clear all tag filters"""
        self.tag_filter_manager.clear_selection()
        self._restore_filtered_view()

    def _apply_tag_filter(self):
        """Filter items by selected tags at UI level (no DB calls)"""
        # Determine which listbox to update
        if self.current_tab == "pasted":
            listbox = self.pasted_listbox
        else:
            listbox = self.copied_listbox

        # Apply filter via manager
        self.tag_filter_manager.apply_filter(listbox)

    def _restore_filtered_view(self):
        """Restore normal unfiltered view by making all rows visible"""
        # Determine which listbox to update
        if self.current_tab == "pasted":
            listbox = self.pasted_listbox
        else:
            listbox = self.copied_listbox

        # Restore view via manager
        self.tag_filter_manager.restore_view(listbox)

    def _reload_item_tags(self, item_id: int, copied_listbox: Gtk.ListBox, pasted_listbox: Gtk.ListBox):
        """Reload tags for a specific clipboard item in both listboxes.

        Args:
            item_id: ID of the item to reload tags for
            copied_listbox: Copied items listbox
            pasted_listbox: Pasted items listbox
        """
        # Reload tags in copied listbox
        for row in copied_listbox:
            if hasattr(row, 'item') and row.item.get('id') == item_id:
                if hasattr(row, '_load_item_tags'):
                    row._load_item_tags()
                break

        # Reload tags in pasted listbox
        for row in pasted_listbox:
            if hasattr(row, 'item') and row.item.get('id') == item_id:
                if hasattr(row, '_load_item_tags'):
                    row._load_item_tags()
                break

    # ========== Tag Manager Methods ==========

    def _on_tag_drag_prepare(self, drag_source, x, y, tag):
        """Prepare data for tag drag operation - delegates to UserTagsManager"""
        return self.user_tags_manager.on_tag_drag_prepare(drag_source, x, y, tag)

    def _on_tag_drag_begin(self, drag_source, drag):
        """Called when tag drag begins - delegates to UserTagsManager"""
        self.user_tags_manager.on_tag_drag_begin(drag_source, drag)

    def _on_tag_dropped_on_item(self, tag_id, item_id):
        """Handle tag drop on an item - delegates to UserTagsManager"""
        self.user_tags_manager.add_tag_to_item(
            tag_id, item_id, self.copied_listbox, self.pasted_listbox
        )


    def _on_create_tag(self, button):
        """Show dialog to create a new tag - delegates to TagDialogManager"""
        self.tag_dialog_manager.show_create_dialog()

    def _on_edit_tag(self, tag_id):
        """Show dialog to edit a tag - delegates to TagDialogManager"""
        self.tag_dialog_manager.show_edit_dialog(tag_id)

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
        """Delete a tag on the server - delegates to UserTagsManager"""
        self.user_tags_manager.delete_tag(tag_id, self)

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
