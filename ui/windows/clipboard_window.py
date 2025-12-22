"""ClipboardWindow - Main application window."""

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
from ui.builders.main_window_builder import MainWindowBuilder
from ui.managers.filter_bar_manager import FilterBarManager
from ui.managers.history_loader_manager import HistoryLoaderManager
from ui.managers.keyboard_shortcut_handler import KeyboardShortcutHandler
from ui.managers.notification_manager import NotificationManager
from ui.managers.search_manager import SearchManager
from ui.managers.sort_manager import SortManager
from ui.managers.tab_manager import TabManager
from ui.managers.tag_dialog_manager import TagDialogManager
from ui.managers.tag_display_manager import TagDisplayManager
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

        # Add global click handler to clear secret authentication when clicking elsewhere
        # Use BUBBLE phase so buttons can handle clicks first, then we clear auth
        click_gesture = Gtk.GestureClick.new()
        click_gesture.set_propagation_phase(Gtk.PropagationPhase.BUBBLE)
        click_gesture.connect("released", self._on_window_clicked)
        self.add_controller(click_gesture)

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

        self.page_size = self.settings.max_page_length

        # Window icon is set through the desktop file and application
        # GTK4/Adwaita doesn't use set_icon() anymore

        # ========== UI Construction via MainWindowBuilder ==========
        builder = MainWindowBuilder(self)
        widgets = builder.build()

        # Store widget references from builder
        self.header = widgets.header
        self.title_stack = widgets.title_stack
        self.button_stack = widgets.button_stack
        self.search_container = widgets.search_container
        self.search_entry = widgets.search_entry
        self.tag_flowbox = widgets.tag_flowbox
        self.main_stack = widgets.main_stack
        self.tab_view = widgets.tab_view
        self.tab_bar = widgets.tab_bar
        self.copied_scrolled = widgets.copied_scrolled
        self.copied_listbox = widgets.copied_listbox
        self.copied_loader = widgets.copied_loader
        self.copied_status_label = widgets.copied_status_label
        self.pasted_scrolled = widgets.pasted_scrolled
        self.pasted_listbox = widgets.pasted_listbox
        self.pasted_loader = widgets.pasted_loader
        self.pasted_status_label = widgets.pasted_status_label
        self.user_tags_group = widgets.user_tags_group
        self.filter_sort_btn = widgets.filter_sort_btn

        # Store settings page spin rows (created by builder)
        # These are needed for _on_save_settings compatibility method
        # (Builder sets these as window attributes via self.window.item_width_spin etc.)

        # Remove builder's filter_bar from main_box (we'll use FilterBarManager's instead)
        widgets.main_box.remove(widgets.filter_bar)

        # Initialize FilterBarManager for filter state management
        self.filter_bar_manager = FilterBarManager(
            on_filter_changed=self._reload_current_tab
        )

        # Add toolbar controls to filter bar
        self.filter_bar_manager.add_toolbar_separator()
        self.filter_sort_btn = self.filter_bar_manager.add_sort_button(
            on_sort_clicked=self._toggle_sort_from_toolbar,
            initial_tooltip="Newest first ↓"
        )
        self.filter_bar_manager.add_jump_to_top_button(
            on_jump_clicked=self._jump_to_top_from_toolbar
        )

        # Build filter bar widget and insert into main_box (after tab_bar)
        # Builder already added: header, search, tab_bar, main_stack, tag_frame
        # We need to insert filter_bar between tab_bar and main_stack
        self.filter_bar_widget = self.filter_bar_manager.build()
        # Insert filter_bar after tab_bar
        widgets.main_box.insert_child_after(self.filter_bar_widget, widgets.tab_bar)

        # Initialize NotificationManager and add its widget
        self.notification_manager = NotificationManager()
        widgets.main_box.append(self.notification_manager.get_widget())

        # Set window content
        self.set_content(widgets.main_box)

        # Store current tab state
        self.current_tab = "copied"

        # Initialize SearchManager
        self.search_manager = SearchManager(
            copied_listbox=self.copied_listbox,
            pasted_listbox=self.pasted_listbox,
            copied_status_label=self.copied_status_label,
            pasted_status_label=self.pasted_status_label,
            get_current_tab=lambda: self.current_tab,
            jump_to_top=self._jump_to_top,
            window=self,
            on_notification=self.show_notification,
        )

        # Initialize SortManager (will be updated after history_loader is created)
        self.sort_manager = None

        # Initialize TabManager (pass the filter_bar widget for show/hide functionality)
        self.tab_manager = TabManager(
            window_instance=self,
            filter_bar=self.filter_bar_widget,
            search_manager=self.search_manager,
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
                self.user_tags_manager.load_user_tags(),
                self.load_tags(),
                self.show_notification("Tag created"),
            ),
            on_tag_updated=lambda: (
                self.user_tags_manager.load_user_tags(),
                self.load_tags(),
            ),
            get_all_tags=lambda: self.all_tags,
        )

        # Tag state
        self.all_tags = []  # All available tags (system + user)
        self.filtered_items = []  # Filtered items when tag filter is active
        self.dragged_tag = None

        # Initialize TagDisplayManager
        self.tag_display_manager = TagDisplayManager(
            tag_flowbox=self.tag_flowbox,
            tag_filter_manager=self.tag_filter_manager,
            copied_listbox=self.copied_listbox,
            pasted_listbox=self.pasted_listbox,
            get_current_tab=lambda: self.current_tab,
            on_tag_drag_prepare=self._on_tag_drag_prepare,
            on_tag_drag_begin=self._on_tag_drag_begin,
            window=self,
        )

        # Initialize HistoryLoaderManager
        self.history_loader = HistoryLoaderManager(
            copied_listbox=self.copied_listbox,
            pasted_listbox=self.pasted_listbox,
            copied_status_label=self.copied_status_label,
            pasted_status_label=self.pasted_status_label,
            copied_loader=self.copied_loader,
            pasted_loader=self.pasted_loader,
            copied_scrolled=self.copied_scrolled,
            pasted_scrolled=self.pasted_scrolled,
            window=self,
            get_active_filters=self.filter_bar_manager.get_active_filters,
            get_search_query=self.search_manager.get_query,
            page_size=self.page_size,
        )

        # Initialize SortManager (after history_loader is created)
        self.sort_manager = SortManager(
            sort_button=self.filter_sort_btn,
            on_history_load=self.history_loader.initial_history_load,
            on_pasted_load=self.history_loader.initial_pasted_load,
            get_active_filters=self.filter_bar_manager.get_active_filters,
            page_size=self.page_size,
        )

        # Position window to the left (again, to ensure it's positioned)
        self.position_manager.position_left()

        # Set up global keyboard shortcut

        # Load tags for filtering
        self.load_tags()

        # Load user tags for tag manager (via manager)
        self.user_tags_manager.load_user_tags()

        # Load clipboard history
        GLib.idle_add(self.history_loader.load_history)

        # Initialize KeyboardShortcutHandler
        self.keyboard_handler = KeyboardShortcutHandler(
            self, self.search_entry, self.copied_listbox
        )

        # Register UI PID with server for cleanup
        GLib.idle_add(self._register_ui_pid_with_server)

        logger.info(
            f"ClipboardWindow initialized in {time.time() - start_time:.2f} seconds"
        )


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
            pagination = self.history_loader.get_pagination_state(list_type)
            if pagination["has_more"] and not pagination["loading"]:
                print(
                    f"[UI] Scrolled to bottom of {list_type} list, loading more..."
                )
                self.history_loader.set_loading(list_type, True)
                if list_type == "copied":
                    GLib.idle_add(self.history_loader.load_more_copied_items)
                else:
                    GLib.idle_add(self.history_loader.load_more_pasted_items)

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

    def _register_ui_pid_with_server(self):
        """Register UI PID with server so server can kill UI on exit"""
        try:
            import websockets

            async def register_pid():
                try:
                    uri = "ws://localhost:8765"
                    async with websockets.connect(uri) as websocket:
                        request = {"action": "register_ui_pid", "pid": os.getpid()}
                        await websocket.send(json.dumps(request))
                        response = await websocket.recv()
                        logger.info(f"UI PID registration response: {response}")
                except Exception as e:
                    logger.error(f"Failed to register UI PID with server: {e}")

            # Run in new event loop since we're in GTK main loop
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(register_pid())
            loop.close()
        except Exception as e:
            logger.error(f"Error in PID registration: {e}")

    def _on_close_request(self, window):
        """Handle window close request - just hide/close the UI, leave server running"""
        logger.info("UI closing, server will continue running in background")
        print("Exiting UI...")
        return False  # Allow window to close

    def _on_focus_changed(self, window, param):
        """Handle window focus changes - clear secret authentication when focus is lost."""
        if not self.is_active():
            # Window lost focus or was minimized - clear secret authentication
            logger.info("Window focus lost, clearing secret authentication")
            self.password_service.clear_authentication()

    def _on_window_clicked(self, gesture, n_press, x, y):
        """Handle clicks anywhere in the window - clear secret authentication.

        This runs in BUBBLE phase AFTER child widgets handle the click.
        Secret buttons claim their events in CAPTURE phase, so if we get here,
        it means the user clicked somewhere other than an action button.
        """
        logger.debug("Window click detected, clearing secret authentication")
        self.password_service.clear_authentication()

    def _reload_current_tab(self):
        """Reload items in the current tab"""
        current_page = self.tab_view.get_selected_page()
        if not current_page:
            return

        is_copied_tab = current_page.get_title() == "Copied"
        if is_copied_tab:
            # Clear and reload copied items
            for row in list(self.copied_listbox):
                self.copied_listbox.remove(row)
            self.history_loader.reset_pagination("copied")
            self.history_loader.load_history()
        else:
            # Clear and reload pasted items
            for row in list(self.pasted_listbox):
                self.pasted_listbox.remove(row)
            self.history_loader.reset_pagination("pasted")
            self.history_loader.load_pasted_history()

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

    def _restore_normal_view(self):
        """Restore normal view when search is cleared"""
        # Reset pagination and reload current tab
        if self.current_tab == "pasted":
            self.history_loader.reset_pagination("pasted")
            GLib.idle_add(self.history_loader.load_pasted_history)
        else:  # copied
            self.history_loader.reset_pagination("copied")
            GLib.idle_add(self.history_loader.reload_copied_with_filters)

    # ========== Builder Compatibility Methods ==========

    def _on_search_changed(self, entry):
        """Compatibility method for MainWindowBuilder - delegates to wrapper"""
        return self._on_search_changed_wrapper(entry)

    def _on_search_activate(self, entry):
        """Compatibility method for MainWindowBuilder - delegates to wrapper"""
        return self._on_search_activate_wrapper(entry)

    def _on_filter_toggled(self, filter_id: str, button: Gtk.ToggleButton):
        """Compatibility method for MainWindowBuilder - delegates to FilterBarManager"""
        return self.filter_bar_manager._on_filter_toggled(filter_id, button)

    def _on_clear_filters(self, button: Gtk.Button = None):
        """Compatibility method for MainWindowBuilder - delegates to FilterBarManager"""
        return self.filter_bar_manager._on_clear_filters(button)

    def _on_save_settings(self, button: Gtk.Button):
        """Compatibility method for MainWindowBuilder - extracts values and delegates"""
        # Extract values from the spin rows (set by builder)
        item_width = int(self.item_width_spin.get_value())
        item_height = int(self.item_height_spin.get_value())
        max_page_length = int(self.page_length_spin.get_value())
        return self._handle_settings_save(item_width, item_height, max_page_length)

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
        """Refresh the tag display area - delegates to TagDisplayManager"""
        self.tag_display_manager.refresh_display(self.all_tags)


    def _clear_tag_filter(self):
        """Clear all tag filters - delegates to TagDisplayManager"""
        self.tag_display_manager.clear_tag_filter()

    def _apply_tag_filter(self):
        """Filter items by selected tags - delegates to TagDisplayManager"""
        self.tag_display_manager.apply_tag_filter()

    def _restore_filtered_view(self):
        """Restore normal unfiltered view - delegates to TagDisplayManager"""
        self.tag_display_manager.restore_filtered_view()

    def _reload_item_tags(self, item_id: int, copied_listbox: Gtk.ListBox, pasted_listbox: Gtk.ListBox):
        """Reload tags for a specific clipboard item - delegates to TagDisplayManager"""
        self.tag_display_manager.reload_item_tags(item_id)

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
