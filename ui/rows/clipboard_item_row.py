"""ClipboardItemRow - Focused on item display and clipboard operations.

Uses extracted components for UI, handles clipboard/WebSocket operations.
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
import websockets

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Gio", "2.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, GdkPixbuf, Gio, GLib, GObject, Gtk, Pango

from ui.components.items import ItemActions, ItemContent, ItemHeader
from ui.rows.handlers import (
    ClipboardOperationsHandler,
    ItemDialogHandler,
    ItemDragDropHandler,
    ItemSecretManager,
    ItemTagManager,
    ItemWebSocketService,
)
from ui.services.clipboard_service import ClipboardService
from ui.services.password_service import PasswordService

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
        self.password_service = PasswordService()

        # Initialize WebSocket service for server communication
        self.ws_service = ItemWebSocketService(
            item=item,
            window=window,
            on_rebuild_content=self._rebuild_content,
            on_update_lock_button=self._update_lock_button_icon,
            on_display_tags=self._display_tags,
        )

        # Initialize clipboard operations handler
        self.clipboard_ops = ClipboardOperationsHandler(
            item=item,
            window=window,
            ws_service=self.ws_service,
            password_service=self.password_service,
            clipboard_service=self.clipboard_service,
        )

        # Initialize dialog handler
        self.dialog_handler = ItemDialogHandler(
            item=item,
            window=window,
            password_service=self.password_service,
            ws_service=self.ws_service,
            get_root=self.get_root,
        )

        # Initialize secret manager
        self.secret_manager = ItemSecretManager(
            item=item,
            window=window,
            password_service=self.password_service,
            ws_service=self.ws_service,
            get_root=self.get_root,
        )

        item_height = self.window.settings.item_height

        self.set_activatable(True)
        self.connect("activate", lambda row: self._on_row_clicked(self))

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        main_box.set_hexpand(True)
        main_box.set_vexpand(False)
        main_box.set_margin_start(12)
        main_box.set_margin_end(12)
        main_box.set_margin_top(8)
        main_box.set_margin_bottom(8)

        # Create viewport to clip content to exact height
        viewport = Gtk.Viewport()
        viewport.set_child(main_box)
        viewport.set_vexpand(False)
        viewport.set_hexpand(True)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_child(viewport)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.EXTERNAL)
        scrolled.set_size_request(-1, item_height - 16)  # Account for margins
        scrolled.set_vexpand(False)
        scrolled.set_hexpand(True)
        scrolled.set_propagate_natural_height(False)
        scrolled.set_propagate_natural_width(True)

        card_frame = Gtk.Frame()
        card_frame.set_vexpand(False)
        card_frame.set_hexpand(True)
        card_frame.add_css_class("clipboard-item-card")
        card_frame.set_child(scrolled)
        card_frame.set_overflow(Gtk.Overflow.HIDDEN)
        self.card_frame = card_frame

        # Apply CSS to set minimum height
        css_provider = Gtk.CssProvider()
        css_data = f"frame {{ min-height: {item_height}px; }}"
        css_provider.load_from_data(css_data.encode())
        card_frame.get_style_context().add_provider(
            css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        self.set_size_request(-1, item_height)
        self.set_vexpand(False)
        self.set_hexpand(True)

        click_gesture = Gtk.GestureClick.new()
        click_gesture.connect("released", self._on_card_clicked)
        card_frame.add_controller(click_gesture)

        # Initialize drag-and-drop handler
        self.drag_drop_handler = ItemDragDropHandler(
            item=item,
            card_frame=card_frame,
            password_service=self.password_service,
            ws_service=self.ws_service,
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
            on_secret=self.secret_manager.handle_secret_action,
            on_delete=self.dialog_handler.handle_delete_action,
        )
        self.actions_widget = self.actions.build()

        # Build header with actions on the right
        header = ItemHeader(
            item=self.item,
            on_name_save=self.ws_service.update_item_name,
            show_pasted_time=self.show_pasted_time,
            search_query=self.search_query,
        )
        self.header_widget = header.build(self.actions_widget)
        main_box.append(self.header_widget)

        # Build and store content widget for later updates
        content = ItemContent(item=self.item, search_query=self.search_query)
        self.content_widget = content.build()
        main_box.append(self.content_widget)

        # Store reference to main_box for rebuilding content
        self.main_box = main_box

        # Add drop target to main_box (not card_frame) to avoid conflict with drag source
        drop_target = Gtk.DropTarget.new(
            GObject.TYPE_STRING, Gdk.DragAction.COPY
        )
        drop_target.connect("drop", lambda dt, val, x, y: self.tag_manager.handle_tag_drop(dt, val, x, y) if self.tag_manager else False)
        main_box.add_controller(drop_target)

        self.overlay = Gtk.Overlay()
        self.overlay.set_child(card_frame)

        # Initialize tag manager
        self.tag_manager = ItemTagManager(
            item=item,
            window=window,
            overlay=self.overlay,
            ws_service=self.ws_service,
            on_tags_action=self._on_tags_action,
        )

        # Build initial tags display using tag manager
        self.tag_manager.display_tags(self.item.get("tags", []))

        self.set_child(self.overlay)

        # Load tags asynchronously from server
        self.ws_service.load_item_tags()

    def _load_item_tags(self):
        """Reload tags for this item - called by TagDisplayManager after drag-and-drop."""
        self.ws_service.load_item_tags()

    def _rebuild_content(self):
        """Rebuild the content area to reflect updated item data."""
        logger.info(f"_rebuild_content called for item {self.item.get('id')}, is_secret={self.item.get('is_secret')}")

        # Remove old content widget
        self.main_box.remove(self.content_widget)

        # Build new content with updated item data
        content = ItemContent(item=self.item, search_query=self.search_query)
        self.content_widget = content.build()

        # Append to main_box (it will be added at the end, which is correct)
        self.main_box.append(self.content_widget)

        # Force GTK to show and redraw the new widgets
        self.content_widget.show()
        self.main_box.queue_draw()
        self.card_frame.queue_draw()

        logger.info(f"_rebuild_content completed for item {self.item.get('id')}")
        return False  # For GLib.idle_add

    def _update_lock_button_icon(self):
        """Update the lock button icon to reflect current secret status."""
        logger.info(f"_update_lock_button_icon called for item {self.item.get('id')}, is_secret={self.item.get('is_secret')}")

        # Rebuild actions with updated item data
        self.actions = ItemActions(
            item=self.item,
            on_copy=self.clipboard_ops.handle_copy_action,
            on_view=self.dialog_handler.handle_view_action,
            on_save=self.dialog_handler.handle_save_action,
            on_tags=self._on_tags_action,
            on_secret=self.secret_manager.handle_secret_action,
            on_delete=self.dialog_handler.handle_delete_action,
        )

        # Remove old header
        self.main_box.remove(self.header_widget)

        # Build new header with updated actions
        new_actions_widget = self.actions.build()
        header = ItemHeader(
            item=self.item,
            on_name_save=self.ws_service.update_item_name,
            show_pasted_time=self.show_pasted_time,
            search_query=self.search_query,
        )
        self.header_widget = header.build(new_actions_widget)

        # Insert header at the beginning (position 0)
        self.main_box.prepend(self.header_widget)

        # Force GTK to show and redraw the new widgets
        self.header_widget.show()
        self.main_box.queue_draw()
        self.card_frame.queue_draw()

        logger.info(f"_update_lock_button_icon completed for item {self.item.get('id')}")
        return False  # For GLib.idle_add


    def _show_auth_required_notification(self):
        """Show notification that authentication is required."""
        self.window.show_notification("Authentication required to drag secret item")
        return False  # For GLib.idle_add

    def _show_fetch_error_notification(self):
        """Show notification that fetching secret content failed."""
        self.window.show_notification("Failed to retrieve secret content")
        return False  # For GLib.idle_add

    def _on_row_clicked(self, row):
        """Copy item to clipboard when row is clicked."""
        logger.info(f"[KEYBOARD] Row clicked for item {self.item.get('id')}")
        self.clipboard_ops.perform_copy_to_clipboard(
            self.item["type"], self.item["id"], self.item["content"]
        )

        # If activated via keyboard shortcut, hide window and auto-paste
        if hasattr(self.window, "keyboard_handler"):
            logger.info(f"[KEYBOARD] activated_via_keyboard = {self.window.keyboard_handler.activated_via_keyboard}")
            if self.window.keyboard_handler.activated_via_keyboard:
                logger.info(
                    "[KEYBOARD] Auto-hiding window and pasting after click"
                )
                self.window.hide()
                self.window.keyboard_handler.activated_via_keyboard = False

                # Wait for focus to return, then simulate paste
                logger.info("[KEYBOARD] Scheduling paste simulation in 150ms")
                GLib.timeout_add(150, self.clipboard_ops.simulate_paste)
            else:
                logger.info("[KEYBOARD] Not activated via keyboard, skipping auto-paste")

    def _on_tags_action(self):
        """Handle tags button click - delegate to tag manager."""
        if self.tag_manager:
            self.tag_manager.handle_tags_action()

    def _display_tags(self, tags):
        """Display tags in the tags overlay - delegate to tag manager."""
        if self.tag_manager:
            self.tag_manager.display_tags(tags)

    def _on_card_clicked(self, gesture, n_press, x, y):
        """Handle card clicks - single click copies."""
        if n_press == 1:
            # Single click - copy to clipboard
            self._on_row_clicked(self)
