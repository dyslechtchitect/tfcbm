"""ClipboardItemRow - Focused on item display and clipboard operations.

Uses extracted components for UI, handles clipboard IPC operations.
"""

import asyncio
import base64
import json
import logging
import os
import tempfile
import threading
import time
import traceback
from pathlib import Path

import gi
# Removed websockets import - using IPC only

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Gio", "2.0")

from gi.repository import Gdk, GdkPixbuf, Gio, GLib, GObject, Gtk, Pango

from ui.components.items import ItemActions, ItemContent, ItemHeader
from ui.rows.handlers import (
    ClipboardOperationsHandler,
    ItemDialogHandler,
    ItemDragDropHandler,
    ItemTagManager,
    ItemIPCService,
)
from ui.services.clipboard_service import ClipboardService

logger = logging.getLogger("TFCBM.UI")


class ClipboardItemRow(Gtk.ListBoxRow):
    """Row displaying a clipboard item with all interactions."""

    def __init__(self, item, window, show_pasted_time=False, search_query=""):
        super().__init__()
        self.item = item
        self.window = window
        self.show_pasted_time = show_pasted_time
        self.search_query = search_query
        self.clipboard_service = ClipboardService()

        # Initialize IPC service for server communication
        self.ipc_service = ItemIPCService(
            item=item,
            window=window,
            on_rebuild_content=self._rebuild_content,
            on_display_tags=self._display_tags,
            on_update_header_name=self._update_header_name,
        )

        # Initialize clipboard operations handler
        self.clipboard_ops = ClipboardOperationsHandler(
            item=item,
            window=window,
            ws_service=self.ipc_service,
            clipboard_service=self.clipboard_service,
        )

        # Initialize dialog handler
        self.dialog_handler = ItemDialogHandler(
            item=item,
            window=window,
            ws_service=self.ipc_service,
            get_root=self.get_root,
            search_query=self.search_query,
        )

        item_height = self.window.settings.item_height

        self.set_activatable(True)
        self.connect("activate", lambda row: self._on_row_clicked(self))

        # Simple container - header will be added directly later
        card_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        card_container.set_hexpand(True)
        card_container.set_vexpand(False)

        # Content box (will scroll)
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        content_box.set_hexpand(True)
        content_box.set_vexpand(False)
        content_box.set_margin_start(12)
        content_box.set_margin_end(12)
        content_box.set_margin_bottom(0)

        # Create viewport for scrollable content
        viewport = Gtk.Viewport()
        viewport.set_child(content_box)
        viewport.set_vexpand(False)
        viewport.set_hexpand(True)

        # ScrolledWindow for content only
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_child(viewport)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.EXTERNAL)

        # SIMPLE FIXED SIZING - min 100px, max 200px content area
        scrolled.set_vexpand(False)
        scrolled.set_hexpand(True)
        scrolled.set_propagate_natural_height(True)  # Let content size naturally
        scrolled.set_propagate_natural_width(True)
        scrolled.set_min_content_height(100)  # Readable minimum
        scrolled.set_max_content_height(200)  # Can expand to 2X

        # Store scrolled for later
        self.scrolled = scrolled
        self.content_box = content_box
        self.card_container = card_container

        card_frame = Gtk.Frame()
        card_frame.set_vexpand(False)
        card_frame.set_hexpand(True)
        card_frame.add_css_class("clipboard-item-card")
        card_frame.set_child(card_container)
        card_frame.set_overflow(Gtk.Overflow.HIDDEN)
        self.card_frame = card_frame

        # ROW sizes to content naturally
        self.set_vexpand(False)
        self.set_hexpand(True)

        click_gesture = Gtk.GestureClick.new()
        click_gesture.connect("released", self._on_card_clicked)
        card_frame.add_controller(click_gesture)

        # Initialize drag-and-drop handler
        self.drag_drop_handler = ItemDragDropHandler(
            item=item,
            card_frame=card_frame,
            ws_service=self.ipc_service,
            on_show_auth_required=self._show_auth_required_notification,
            on_show_fetch_error=self._show_fetch_error_notification,
        )

        # Set up drag source
        drag_source = Gtk.DragSource.new()
        drag_source.set_actions(Gdk.DragAction.COPY)
        drag_source.connect("prepare", self.drag_drop_handler.on_drag_prepare)
        drag_source.connect("drag-begin", self.drag_drop_handler.on_drag_begin)
        card_frame.add_controller(drag_source)

        # Pre-fetch file content for drag-and-drop
        if item.get("type") == "file":
            self.drag_drop_handler.prefetch_file_for_dnd()

        # Create placeholder for tag manager (will be initialized after overlay creation)
        self.tag_manager = None

        # Build actions first
        self.actions = ItemActions(
            item=self.item,
            on_copy=self.clipboard_ops.handle_copy_action,
            on_view=self.dialog_handler.handle_view_action,
            on_save=self.dialog_handler.handle_save_action,
            on_tags=self._on_tags_action,
            on_delete=self.dialog_handler.handle_delete_action,
        )
        self.actions_widget = self.actions.build()

        # Build header with actions on the right
        self.header = ItemHeader(
            item=self.item,
            on_name_save=self.ipc_service.update_item_name,
            on_favorite_toggle=self._on_favorite_toggle,
            show_pasted_time=self.show_pasted_time,
            search_query=self.search_query,
        )
        self.header_widget = self.header.build(self.actions_widget)

        # Add margins to header widget (since we removed the wrapper header_box)
        self.header_widget.set_margin_start(12)
        self.header_widget.set_margin_end(12)
        self.header_widget.set_margin_top(8)
        self.header_widget.set_margin_bottom(4)

        # Append header and scrolled to card_container
        self.card_container.append(self.header_widget)
        self.card_container.append(self.scrolled)

        # Build and store content widget for later updates
        content = ItemContent(item=self.item, search_query=self.search_query)
        self.content_widget = content.build()
        self.content_box.append(self.content_widget)

        # Store reference to content_box for rebuilding content
        self.main_box = self.content_box

        # Add drop target to content_box (not card_frame) to avoid conflict with drag source
        drop_target = Gtk.DropTarget.new(
            GObject.TYPE_STRING, Gdk.DragAction.COPY
        )
        drop_target.connect("drop", lambda dt, val, x, y: self.tag_manager.handle_tag_drop(dt, val, x, y) if self.tag_manager else False)
        drop_target.connect("enter", lambda dt, x, y: self._on_drag_enter(card_frame))
        drop_target.connect("leave", lambda dt: self._on_drag_leave(card_frame))
        self.content_box.add_controller(drop_target)

        self.overlay = Gtk.Overlay()
        self.overlay.set_child(card_frame)

        # Initialize tag manager
        self.tag_manager = ItemTagManager(
            item=item,
            window=window,
            overlay=self.overlay,
            ws_service=self.ipc_service,
            on_tags_action=self._on_tags_action,
        )

        # Set the tags button reference for popover anchoring
        if hasattr(self.actions, 'tags_button'):
            self.tag_manager.set_tags_button(self.actions.tags_button)

        # Build initial tags display using tag manager
        self.tag_manager.display_tags(self.item.get("tags", []))

        self.set_child(self.overlay)

        # Load tags asynchronously from server
        self.ipc_service.load_item_tags()

    def _load_item_tags(self):
        """Reload tags for this item - called by TagDisplayManager after drag-and-drop."""
        self.ipc_service.load_item_tags()

    def _on_drag_enter(self, card_frame):
        """Handle drag enter - brighten card without border outline."""
        # Add CSS class to brighten the card
        card_frame.add_css_class("drag-hover")
        return Gdk.DragAction.COPY

    def _on_drag_leave(self, card_frame):
        """Handle drag leave - remove brightening effect."""
        # Remove CSS class
        card_frame.remove_css_class("drag-hover")

    def _rebuild_content(self):
        """Rebuild the content area to reflect updated item data."""
        logger.info(f"_rebuild_content called for item {self.item.get('id')}")

        # Remove old content widget
        self.main_box.remove(self.content_widget)

        # Build new content with updated item data
        content = ItemContent(item=self.item, search_query=self.search_query)
        self.content_widget = content.build()

        # Append to main_box (it will be added at the end, which is correct)
        self.main_box.append(self.content_widget)

        self.scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.EXTERNAL)

        # Force GTK to show and redraw the new widgets
        self.content_widget.show()
        self.main_box.queue_draw()
        self.card_frame.queue_draw()

        logger.info(f"_rebuild_content completed for item {self.item.get('id')}")
        return False  # For GLib.idle_add

    def _update_header_name(self):
        """Update the name entry field in the header to show the current item name."""
        logger.info(f"_update_header_name called for item {self.item.get('id')}, name={self.item.get('name')}")

        if hasattr(self, 'header') and self.header and hasattr(self.header, 'name_entry') and self.header.name_entry:
            item_name = self.item.get("name") or ""
            self.header.name_entry.set_text(item_name)
            logger.info(f"Updated header name entry to: '{item_name}'")
        else:
            logger.warning("Could not find header or name_entry to update")

        return False  # For GLib.idle_add


    def _show_auth_required_notification(self):
        """Show notification that authentication is required."""
        self.window.show_notification("Authentication required to drag protected item")
        return False  # For GLib.idle_add

    def _show_fetch_error_notification(self):
        """Show notification that fetching secret content failed."""
        self.window.show_notification("Failed to retrieve secret content")
        return False  # For GLib.idle_add

    def _on_row_clicked(self, row):
        """Copy item to clipboard when row is clicked."""
        logger.info(f"[KEYBOARD] Row clicked for item {self.item.get('id')}")

        # Copy to clipboard (handles authentication for secrets)
        copy_success = self.clipboard_ops.perform_copy_to_clipboard(
            self.item["type"], self.item["id"], self.item["content"]
        )

        # If copy failed (e.g., authentication cancelled), don't hide window or paste
        if not copy_success:
            logger.info("[KEYBOARD] Copy failed or cancelled, keeping window visible")
            if hasattr(self.window, "keyboard_handler"):
                self.window.keyboard_handler.activated_via_keyboard = False
            return

        # If activated via keyboard shortcut, hide window if refocus_on_copy is enabled
        if hasattr(self.window, "keyboard_handler"):
            logger.info(f"[KEYBOARD] activated_via_keyboard = {self.window.keyboard_handler.activated_via_keyboard}")
            if self.window.keyboard_handler.activated_via_keyboard:
                # Check if refocus_on_copy setting is enabled
                refocus_on_copy = self.window.settings.refocus_on_copy
                logger.info(f"[KEYBOARD] refocus_on_copy setting = {refocus_on_copy}")

                if refocus_on_copy:
                    logger.info("[KEYBOARD] Hiding window and refocusing previous app")
                    self.window.hide()
                    self.window.keyboard_handler.activated_via_keyboard = False
                else:
                    logger.info("[KEYBOARD] refocus_on_copy disabled, keeping window visible")
                    self.window.keyboard_handler.activated_via_keyboard = False
            else:
                logger.info("[KEYBOARD] Not activated via keyboard, skipping auto-hide")

    def _on_tags_action(self):
        """Handle tags button click - delegate to tag manager."""
        if self.tag_manager:
            self.tag_manager.handle_tags_action()

    def _display_tags(self, tags):
        """Display tags in the tags overlay - delegate to tag manager."""
        if self.tag_manager:
            self.tag_manager.display_tags(tags)

    def _on_favorite_toggle(self, item_id: int, is_favorite: bool):
        """Handle favorite toggle action."""
        self.ipc_service.toggle_favorite(item_id, is_favorite)

        # Notify user about favorite status and retention policy
        if is_favorite:
            self.window.show_notification("Item marked as favorite - won't be auto-deleted")
        else:
            self.window.show_notification("Item unmarked as favorite")

    def _on_card_clicked(self, gesture, n_press, x, y):
        """Handle card clicks - single click copies."""
        if n_press == 1:
            # Single click - copy to clipboard
            self._on_row_clicked(self)
