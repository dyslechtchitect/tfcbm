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

from ui.components.items import ItemActions, ItemContent, ItemHeader, ItemTags
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
        self._last_paste_time = 0
        self._file_temp_path = None
        self.clipboard_service = ClipboardService()

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

        drop_target = Gtk.DropTarget.new(
            GObject.TYPE_STRING, Gdk.DragAction.COPY
        )
        drop_target.connect("drop", self._on_tag_drop)
        card_frame.add_controller(drop_target)

        click_gesture = Gtk.GestureClick.new()
        click_gesture.connect("released", self._on_card_clicked)
        card_frame.add_controller(click_gesture)

        drag_source = Gtk.DragSource.new()
        drag_source.set_actions(Gdk.DragAction.COPY)
        drag_source.connect("prepare", self._on_drag_prepare)
        drag_source.connect("drag-begin", self._on_drag_begin)
        card_frame.add_controller(drag_source)

        if item.get("type") == "file":
            self._prefetch_file_for_dnd()

        # Build actions first
        self.actions = ItemActions(
            item=self.item,
            on_copy=self._on_copy_action,
            on_view=self._on_view_action,
            on_save=self._on_save_action,
            on_tags=self._on_tags_action,
            on_delete=self._on_delete_action,
        )
        actions_widget = self.actions.build()

        # Build header with actions on the right
        header = ItemHeader(
            item=self.item,
            on_name_save=self._update_item_name,
            show_pasted_time=self.show_pasted_time,
            search_query=self.search_query,
        )
        main_box.append(header.build(actions_widget))

        content = ItemContent(item=self.item, search_query=self.search_query)
        main_box.append(content.build())

        self.overlay = Gtk.Overlay()
        self.overlay.set_child(card_frame)

        # Build initial tags display
        tags = ItemTags(
            tags=self.item.get("tags", []), on_click=self._on_tags_action
        )
        self.tags_widget = tags.build()
        self.overlay.add_overlay(self.tags_widget)

        self.set_child(self.overlay)

        # Load tags asynchronously from server
        self._load_item_tags()

    def _on_row_clicked(self, row):
        """Copy item to clipboard when row is clicked."""
        self._perform_copy_to_clipboard(
            self.item["type"], self.item["id"], self.item["content"]
        )

        # If activated via keyboard shortcut, hide window and auto-paste
        if hasattr(self.window, "activated_via_keyboard"):
            if self.window.activated_via_keyboard:
                logger.info(
                    "[KEYBOARD] Auto-hiding window and pasting after click"
                )
                self.window.hide()
                self.window.activated_via_keyboard = False

                # Wait for focus to return, then simulate paste
                GLib.timeout_add(150, self._simulate_paste)

    def _simulate_paste(self):
        """Simulate Ctrl+V paste after window is hidden."""
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
                logger.info("[KEYBOARD] Simulated Ctrl+V paste with xdotool")
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
                logger.info("[KEYBOARD] Simulated Ctrl+V paste with ydotool")
                return False
            except Exception as e:
                logger.error(f"[KEYBOARD] ydotool failed: {e}")

        # No tool available
        logger.warning(
            "[KEYBOARD] Neither xdotool nor ydotool found. "
            "Auto-paste disabled."
        )
        return False

    def _on_copy_action(self):
        """Handle copy button click."""
        self._perform_copy_to_clipboard(
            self.item["type"], self.item["id"], self.item["content"]
        )

    def _on_view_action(self):
        """Handle view button click - show full item dialog."""
        self._show_view_dialog()

    def _on_save_action(self):
        """Handle save button click - show save file dialog."""
        self._show_save_dialog()

    def _on_tags_action(self):
        """Handle tags button click - show tags popover."""
        self._show_tags_popover()

    def _load_item_tags(self):
        """Load and display tags for this item asynchronously."""

        def run_load():
            try:

                async def fetch_tags():
                    uri = "ws://localhost:8765"
                    async with websockets.connect(uri) as websocket:
                        request = {
                            "action": "get_item_tags",
                            "item_id": self.item.get("id"),
                        }
                        await websocket.send(json.dumps(request))
                        response = await websocket.recv()
                        data = json.loads(response)

                        if data.get("type") == "item_tags":
                            tags = data.get("tags", [])
                            # Store tags in item for filtering
                            self.item["tags"] = tags
                            # Update UI on main thread
                            GLib.idle_add(self._display_tags, tags)

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(fetch_tags())
            except Exception as e:
                logger.error(f"[UI] Error loading item tags: {e}")

        threading.Thread(target=run_load, daemon=True).start()

    def _display_tags(self, tags):
        """Display tags in the tags overlay."""
        # Remove old tags widget
        if self.tags_widget:
            self.overlay.remove_overlay(self.tags_widget)

        # Create new tags widget
        tags_component = ItemTags(tags=tags, on_click=self._on_tags_action)
        self.tags_widget = tags_component.build()

        # Add new tags widget to overlay
        self.overlay.add_overlay(self.tags_widget)

        return False  # For GLib.idle_add

    def _on_delete_action(self):
        """Handle delete button click - show confirmation dialog."""
        window = self.get_root()

        # Create confirmation dialog
        dialog = Adw.AlertDialog.new(
            "Delete this item?",
            "This item will be permanently removed from your clipboard history.",
        )

        dialog.add_response("cancel", "Nah")
        dialog.add_response("delete", "Yeah")
        dialog.set_response_appearance(
            "delete", Adw.ResponseAppearance.SUGGESTED
        )
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        def on_response(dialog, response):
            if response == "delete":
                self._delete_item_from_server(self.item["id"])

        dialog.connect("response", on_response)
        dialog.present(window)

    def _perform_copy_to_clipboard(self, item_type, item_id, content=None):
        """Copy item to clipboard."""
        clipboard = Gdk.Display.get_default().get_clipboard()
        if not clipboard:
            self.window.show_notification("Error: Could not access clipboard.")
            return

        try:
            if item_type == "text" or item_type == "url":
                if content:
                    # Check if item has formatted content
                    format_type = self.item.get("format_type")
                    formatted_content = self.item.get("formatted_content")

                    if format_type and formatted_content:
                        # Use formatted text copy
                        self.clipboard_service.copy_formatted_text(
                            content, formatted_content, format_type
                        )
                        self.window.show_notification(
                            f"{'URL' if item_type == 'url' else 'Text'} with {format_type.upper()} formatting copied"
                        )
                    else:
                        # Use plain text copy
                        self.clipboard_service.copy_text(content)
                        self.window.show_notification(
                            f"{'URL' if item_type == 'url' else 'Text'} copied to clipboard"
                        )
                    self._record_paste(item_id)
                else:
                    self.window.show_notification(
                        "Error copying: content is empty."
                    )
            elif item_type == "file":
                self.window.show_notification("Loading file...")
                self._copy_file_to_clipboard(item_id, content, clipboard)
            elif item_type.startswith("image/") or item_type == "screenshot":
                self.window.show_notification("Loading full image...")
                self._copy_full_image_to_clipboard(item_id, clipboard)
        except Exception as e:
            self.window.show_notification(f"Error copying: {str(e)}")

    def _copy_full_image_to_clipboard(self, item_id, clipboard):
        """Fetch and copy full image to clipboard."""

        def fetch_and_copy():
            try:

                async def get_full_image():
                    uri = "ws://localhost:8765"
                    max_size = 5 * 1024 * 1024
                    async with websockets.connect(
                        uri, max_size=max_size
                    ) as websocket:
                        request = {"action": "get_full_image", "id": item_id}
                        await websocket.send(json.dumps(request))

                        response = await websocket.recv()
                        data = json.loads(response)

                        if (
                            data.get("type") == "full_image"
                            and data.get("id") == item_id
                        ):
                            image_b64 = data.get("content")
                            image_data = base64.b64decode(image_b64)

                            loader = GdkPixbuf.PixbufLoader()
                            loader.write(image_data)
                            loader.close()
                            pixbuf = loader.get_pixbuf()

                            def copy_to_clipboard():
                                try:
                                    success, png_bytes = (
                                        pixbuf.save_to_bufferv("png", [], [])
                                    )
                                    if not success:
                                        raise Exception(
                                            "Failed to convert image to PNG"
                                        )

                                    gbytes = GLib.Bytes.new(png_bytes)
                                    content = (
                                        Gdk.ContentProvider.new_for_bytes(
                                            "image/png", gbytes
                                        )
                                    )
                                    clipboard.set_content(content)

                                    self.window.show_notification(
                                        f"📷 Full image copied "
                                        f"({pixbuf.get_width()}x{pixbuf.get_height()})"
                                    )
                                    self._record_paste(item_id)
                                except Exception as e:
                                    self.window.show_notification(
                                        f"Error copying: {str(e)}"
                                    )
                                return False

                            GLib.idle_add(copy_to_clipboard)

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(get_full_image())

            except Exception:
                GLib.idle_add(
                    lambda: self.window.show_notification(f"Error: {str(e)}")
                    or False
                )

        threading.Thread(target=fetch_and_copy, daemon=True).start()

    def _copy_file_to_clipboard(self, item_id, file_metadata, clipboard):
        """Copy file or folder to clipboard."""
        is_directory = file_metadata.get("is_directory", False)

        if is_directory:
            self._copy_folder_to_clipboard(item_id, file_metadata, clipboard)
        else:
            self._copy_regular_file_to_clipboard(
                item_id, file_metadata, clipboard
            )

    def _copy_folder_to_clipboard(self, item_id, file_metadata, clipboard):
        """Copy folder to clipboard if it still exists."""

        def copy_folder():
            try:
                original_path = file_metadata.get("original_path", "")
                folder_name = file_metadata.get("name", "folder")

                if original_path and Path(original_path).exists():

                    def copy_to_clipboard():
                        try:
                            gfile = Gio.File.new_for_path(original_path)
                            file_list = Gdk.FileList.new_from_array([gfile])
                            content_provider = (
                                Gdk.ContentProvider.new_for_value(file_list)
                            )
                            clipboard.set_content(content_provider)

                            self.window.show_notification(
                                f"📁 Folder copied: {folder_name}"
                            )
                            self._record_paste(item_id)
                        except Exception as e:
                            self.window.show_notification(
                                f"Error copying folder: {str(e)}"
                            )
                        return False

                    GLib.idle_add(copy_to_clipboard)
                else:
                    GLib.idle_add(
                        lambda: self.window.show_notification(
                            "Folder no longer exists at original location"
                        )
                        or False
                    )
            except Exception:
                GLib.idle_add(
                    lambda: self.window.show_notification(
                        f"Error copying folder: {str(e)}"
                    )
                    or False
                )

        threading.Thread(target=copy_folder, daemon=True).start()

    def _copy_regular_file_to_clipboard(
        self, item_id, file_metadata, clipboard
    ):
        """Fetch file from server and copy to clipboard."""

        def fetch_and_copy():
            try:

                async def get_full_file():
                    uri = "ws://localhost:8765"
                    max_size = 100 * 1024 * 1024
                    async with websockets.connect(
                        uri, max_size=max_size
                    ) as websocket:
                        request = {"action": "get_full_image", "id": item_id}
                        await websocket.send(json.dumps(request))

                        response = await websocket.recv()
                        data = json.loads(response)

                        if (
                            data.get("type") == "full_file"
                            and data.get("id") == item_id
                        ):
                            file_b64 = data.get("content")
                            file_data = base64.b64decode(file_b64)

                            file_name = file_metadata.get(
                                "name", "clipboard_file"
                            )

                            temp_dir = (
                                Path(tempfile.gettempdir()) / "tfcbm_files"
                            )
                            temp_dir.mkdir(exist_ok=True)
                            temp_file_path = temp_dir / file_name

                            with open(temp_file_path, "wb") as f:
                                f.write(file_data)

                            def copy_to_clipboard():
                                try:
                                    gfile = Gio.File.new_for_path(
                                        str(temp_file_path)
                                    )
                                    file_list = Gdk.FileList.new_from_array(
                                        [gfile]
                                    )
                                    content_provider = (
                                        Gdk.ContentProvider.new_for_value(
                                            file_list
                                        )
                                    )
                                    clipboard.set_content(content_provider)

                                    self.window.show_notification(
                                        f"📄 File copied: {file_name}"
                                    )
                                    self._record_paste(item_id)
                                except Exception as e:
                                    self.window.show_notification(
                                        f"Error copying file: {str(e)}"
                                    )
                                return False

                            GLib.idle_add(copy_to_clipboard)

                asyncio.run(get_full_file())

            except Exception:
                GLib.idle_add(
                    lambda: self.window.show_notification(
                        f"Error copying file: {str(e)}"
                    )
                    or False
                )

        threading.Thread(target=fetch_and_copy, daemon=True).start()

    def _record_paste(self, item_id):
        """Record that this item was pasted."""
        current_time = time.time()
        if current_time - self._last_paste_time < 1.0:
            return

        self._last_paste_time = current_time

        def record():
            try:

                async def send_record():
                    uri = "ws://localhost:8765"
                    async with websockets.connect(uri) as websocket:
                        request = {"action": "record_paste", "id": item_id}
                        await websocket.send(json.dumps(request))
                        await websocket.recv()

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(send_record())
            except Exception as e:
                print(f"Error recording paste: {e}")

        threading.Thread(target=record, daemon=True).start()

    def _update_item_name(self, item_id, name):
        """Update item name on server."""
        # Update local item data immediately
        self.item["name"] = name

        def update():
            try:

                async def send_update():
                    uri = "ws://localhost:8765"
                    async with websockets.connect(uri) as websocket:
                        request = {
                            "action": "update_item_name",
                            "item_id": item_id,
                            "name": name,
                        }
                        await websocket.send(json.dumps(request))
                        response = await websocket.recv()
                        data = json.loads(response)

                        if data.get("type") == "item_name_updated":
                            if data.get("success"):
                                logger.info(
                                    f"[UI] Name updated for item {item_id}: '{name}'"
                                )
                            else:
                                logger.error(
                                    f"[UI] Failed to update name for item {item_id}: {data.get('error', 'Unknown error')}"
                                )
                        else:
                            logger.warning(
                                f"[UI] Unexpected response updating name: {data}"
                            )

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(send_update())
            except Exception as e:
                logger.error(f"[UI] Error updating name: {e}")

        threading.Thread(target=update, daemon=True).start()

    def _delete_item_from_server(self, item_id):
        """Send delete request to server via WebSocket."""

        def send_delete():
            try:

                async def delete_item():
                    uri = "ws://localhost:8765"
                    async with websockets.connect(uri) as websocket:
                        request = {"action": "delete_item", "id": item_id}
                        await websocket.send(json.dumps(request))
                        response = await websocket.recv()
                        data = json.loads(response)

                        if data.get("status") == "success":
                            GLib.idle_add(
                                lambda: self.window.show_notification(
                                    "Item deleted"
                                )
                                or False
                            )
                        else:
                            GLib.idle_add(
                                lambda: self.window.show_notification(
                                    "Failed to delete item"
                                )
                                or False
                            )

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(delete_item())
            except Exception as e:
                print(f"Error deleting item: {e}")
                GLib.idle_add(
                    lambda: self.window.show_notification(
                        f"Error deleting: {str(e)}"
                    )
                    or False
                )

        threading.Thread(target=send_delete, daemon=True).start()

    def _show_tags_popover(self):
        """Show popover to manage tags for this item."""
        # Create popover
        popover = Gtk.Popover()
        # Anchor to the tags button if available, otherwise the row
        if hasattr(self, "actions") and hasattr(self.actions, "tags_button"):
            popover.set_parent(self.actions.tags_button)
            popover.set_position(Gtk.PositionType.BOTTOM)
        else:
            popover.set_parent(self)
        popover.set_autohide(True)

        # Content box
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content_box.set_margin_top(12)
        content_box.set_margin_bottom(12)
        content_box.set_margin_start(12)
        content_box.set_margin_end(12)

        # Title
        title = Gtk.Label()
        title.set_markup("<b>Manage Tags</b>")
        title.set_halign(Gtk.Align.START)
        content_box.append(title)

        # Scrollable tag list
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_max_content_height(300)
        scroll.set_propagate_natural_height(True)

        # Tag list box
        tag_list = Gtk.ListBox()
        tag_list.set_selection_mode(Gtk.SelectionMode.NONE)
        tag_list.add_css_class("boxed-list")

        # Get item's current tags
        item_id = self.item.get("id")
        item_tags = self.item.get("tags", [])
        item_tag_ids = [
            tag.get("id") for tag in item_tags if isinstance(tag, dict)
        ]

        # Add all tags as checkbuttons
        if hasattr(self.window, "all_tags"):
            for tag in self.window.all_tags:
                # Skip system tags
                if tag.get("is_system"):
                    continue

                tag_id = tag.get("id")
                tag_name = tag.get("name", "")
                tag_color = tag.get("color", "#9a9996")

                # Create row with checkbutton
                row = Gtk.ListBoxRow()
                row_box = Gtk.Box(
                    orientation=Gtk.Orientation.HORIZONTAL, spacing=12
                )
                row_box.set_margin_top(6)
                row_box.set_margin_bottom(6)
                row_box.set_margin_start(6)
                row_box.set_margin_end(6)

                # Color indicator
                color_box = Gtk.Box()
                color_box.set_size_request(16, 16)
                css_provider = Gtk.CssProvider()
                css_data = f"box {{ background-color: {tag_color}; border-radius: 3px; }}"
                css_provider.load_from_data(css_data.encode())
                color_box.get_style_context().add_provider(
                    css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                )
                row_box.append(color_box)

                # Checkbutton with tag name
                check = Gtk.CheckButton()
                check.set_label(tag_name)
                check.set_hexpand(True)
                check.set_active(tag_id in item_tag_ids)
                check.connect(
                    "toggled",
                    lambda cb, tid=tag_id, iid=item_id: self._on_tag_toggle(
                        cb, tid, iid, popover
                    ),
                )
                row_box.append(check)

                row.set_child(row_box)
                tag_list.append(row)

            # No tags message
            if not any(
                not tag.get("is_system") for tag in self.window.all_tags
            ):
                no_tags_label = Gtk.Label()
                no_tags_label.set_markup(
                    "<i>No custom tags available.\nCreate tags in the Tags tab.</i>"
                )
                no_tags_label.set_justify(Gtk.Justification.CENTER)
                content_box.append(no_tags_label)

        scroll.set_child(tag_list)
        content_box.append(scroll)

        popover.set_child(content_box)
        popover.popup()

    def _on_tag_drop(self, drop_target, value, x, y):
        """Handle tag drop on item."""
        tag_id = value
        item_id = self.item.get("id")
        if hasattr(self.window, "_on_tag_dropped_on_item"):
            self.window._on_tag_dropped_on_item(tag_id, item_id)
        return True

    def _on_tag_toggle(self, checkbutton, tag_id, item_id, popover):
        """Handle tag checkbox toggle."""
        is_active = checkbutton.get_active()

        def send_tag_update():
            try:

                async def update_tag():
                    uri = "ws://localhost:8765"
                    async with websockets.connect(uri) as websocket:
                        action = "add_tag" if is_active else "remove_tag"
                        request = {
                            "action": action,
                            "item_id": item_id,
                            "tag_id": tag_id,
                        }
                        await websocket.send(json.dumps(request))
                        response = await websocket.recv()
                        data = json.loads(response)

                        if data.get("type") in ["tag_added", "tag_removed"]:
                            # Reload tags for this item
                            GLib.idle_add(self._load_item_tags)
                            # Notify window to refresh if needed
                            if hasattr(self.window, "_on_item_tags_changed"):
                                GLib.idle_add(
                                    self.window._on_item_tags_changed, item_id
                                )

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(update_tag())
            except Exception as e:
                logger.error(f"[UI] Error toggling tag: {e}")
                # Revert checkbox on error
                GLib.idle_add(lambda: checkbutton.set_active(not is_active))

        threading.Thread(target=send_tag_update, daemon=True).start()

    def _on_card_clicked(self, gesture, n_press, x, y):
        """Handle card clicks - single click copies."""
        if n_press == 1:
            # Single click - copy to clipboard
            self._on_row_clicked(self)

    def _on_drag_prepare(self, drag_source, x, y):
        """Prepare data for drag operation."""
        item_type = self.item.get("type", "")
        item_id = self.item.get("id")

        print(
            f"[DND] _on_drag_prepare called for type: {item_type}, id: {item_id}"
        )

        # Handle different content types
        if item_type == "text" or item_type == "url":
            # Text content - provide as text/plain
            content = self.item.get("content", "")
            if isinstance(content, bytes):
                content = content.decode("utf-8", errors="ignore")
            value = GObject.Value(str, content)
            return Gdk.ContentProvider.new_for_value(value)

        elif item_type.startswith("image/") or item_type == "screenshot":
            # Image content - provide multiple formats for maximum compatibility
            try:
                # Use thumbnail data (already loaded) instead of full image
                thumbnail_b64 = self.item.get("thumbnail")
                print(
                    f"[DND] Thumbnail data available: {thumbnail_b64 is not None}, "
                    f"length: {len(thumbnail_b64) if thumbnail_b64 else 0}"
                )
                if thumbnail_b64:
                    # Thumbnail is base64-encoded, decode it first
                    image_bytes = base64.b64decode(thumbnail_b64)

                    # Convert PNG bytes to Gdk.Texture
                    pixbuf = GdkPixbuf.Pixbuf.new_from_stream(
                        Gio.MemoryInputStream.new_from_bytes(
                            GLib.Bytes.new(image_bytes)
                        ),
                        None,
                    )
                    texture = Gdk.Texture.new_for_pixbuf(pixbuf)

                    # Create JPEG version using temp file (for immediate use)
                    jpeg_fd, jpeg_path = tempfile.mkstemp(suffix=".jpg")
                    try:
                        os.close(jpeg_fd)
                        pixbuf.savev(jpeg_path, "jpeg", [], [])
                        with open(jpeg_path, "rb") as f:
                            jpeg_bytes = f.read()
                    finally:
                        try:
                            os.unlink(jpeg_path)
                        except Exception:
                            pass

                    # Create BMP version using temp file (for immediate use)
                    bmp_fd, bmp_path = tempfile.mkstemp(suffix=".bmp")
                    try:
                        os.close(bmp_fd)
                        pixbuf.savev(bmp_path, "bmp", [], [])
                        with open(bmp_path, "rb") as f:
                            bmp_bytes = f.read()
                    finally:
                        try:
                            os.unlink(bmp_path)
                        except Exception:
                            pass

                    # Provide MULTIPLE formats for maximum compatibility
                    providers = []

                    # PNG bytes (lossless) - FIRST for web browsers
                    providers.append(
                        Gdk.ContentProvider.new_for_bytes(
                            "image/png", GLib.Bytes.new(image_bytes)
                        )
                    )

                    # JPEG bytes (most compatible)
                    providers.append(
                        Gdk.ContentProvider.new_for_bytes(
                            "image/jpeg", GLib.Bytes.new(jpeg_bytes)
                        )
                    )

                    # BMP bytes (universal)
                    providers.append(
                        Gdk.ContentProvider.new_for_bytes(
                            "image/bmp", GLib.Bytes.new(bmp_bytes)
                        )
                    )

                    # Texture provider (GTK4)
                    tex_value = GObject.Value()
                    tex_value.init(Gdk.Texture)
                    tex_value.set_object(texture)
                    providers.append(
                        Gdk.ContentProvider.new_for_value(tex_value)
                    )

                    # Pixbuf provider (GTK3/4)
                    pb_value = GObject.Value()
                    pb_value.init(GdkPixbuf.Pixbuf)
                    pb_value.set_object(pixbuf)
                    providers.append(
                        Gdk.ContentProvider.new_for_value(pb_value)
                    )

                    # Union all providers
                    provider = Gdk.ContentProvider.new_union(providers)
                    print(
                        f"[DND] Created multi-format content provider "
                        f"({pixbuf.get_width()}x{pixbuf.get_height()}, "
                        f"PNG:{len(image_bytes)}, JPEG:{len(jpeg_bytes)}, "
                        f"BMP:{len(bmp_bytes)})"
                    )
                    return provider
                else:
                    print(
                        f"[DND] No thumbnail data in item! "
                        f"Keys: {list(self.item.keys())}"
                    )
            except Exception as e:
                print(f"[DND] Error preparing image: {e}")
                traceback.print_exc()

        elif item_type == "file":
            # Use pre-fetched temp file/folder for drag-and-drop
            if self._file_temp_path and os.path.exists(self._file_temp_path):
                file_uri = f"file://{self._file_temp_path}"
                uri_list_bytes = file_uri.encode("utf-8")
                provider = Gdk.ContentProvider.new_for_bytes(
                    "text/uri-list", GLib.Bytes.new(uri_list_bytes)
                )
                print(f"[DND] Providing file/folder URI: {file_uri}")
                return provider
            else:
                print(
                    "[DND] File/folder not ready for drag "
                    "(temp file not available)"
                )
                return None

        return None

    def _on_drag_begin(self, drag_source, drag):
        """Called when drag begins - set drag icon."""
        print("[DND] _on_drag_begin called")
        # Use a small preview of the item as drag icon
        icon = Gtk.WidgetPaintable.new(self.card_frame)
        drag_source.set_icon(icon, 0, 0)
        print("[DND] Drag icon set")

    def _prefetch_file_for_dnd(self):
        """Pre-fetch file content and save to temp location for drag-and-drop."""

        def fetch_and_save():
            print("[DND] Background thread started for pre-fetch")
            try:

                async def get_file():
                    item_id = self.item.get("id")
                    print(f"[DND] Async get_file() started for item {item_id}")
                    uri = "ws://localhost:8765"
                    max_size = 100 * 1024 * 1024  # 100MB for files

                    print(f"[DND] Pre-fetching file for item {item_id}")

                    try:
                        async with websockets.connect(
                            uri, max_size=max_size
                        ) as websocket:
                            # Use same action as Save button: get_full_image
                            request = {
                                "action": "get_full_image",
                                "id": item_id,
                            }
                            await websocket.send(json.dumps(request))

                            # Wait for response
                            response = await websocket.recv()
                            data = json.loads(response)

                            if (
                                data.get("type") == "full_file"
                                and data.get("id") == item_id
                            ):
                                file_b64 = data.get("content")
                                filename = data.get(
                                    "filename", f"file_{item_id}"
                                )

                                if file_b64:
                                    # Decode file content
                                    file_bytes = base64.b64decode(file_b64)

                                    # Create temp file with original filename
                                    fd, temp_path = tempfile.mkstemp(
                                        suffix=f"_{filename}"
                                    )
                                    try:
                                        os.write(fd, file_bytes)
                                    finally:
                                        os.close(fd)

                                    self._file_temp_path = temp_path
                                    print(
                                        f"[DND] Pre-fetched file to: {temp_path} "
                                        f"({len(file_bytes)} bytes)"
                                    )
                                else:
                                    # Empty content - likely a folder
                                    # Check if item has original_path in metadata
                                    file_metadata = self.item.get(
                                        "content", {}
                                    )
                                    original_path = file_metadata.get(
                                        "original_path"
                                    )
                                    print(
                                        f"[DND] Checking for original_path in "
                                        f"content field: {original_path}"
                                    )
                                    if original_path and os.path.exists(
                                        original_path
                                    ):
                                        self._file_temp_path = original_path
                                        print(
                                            f"[DND] Using original folder path: "
                                            f"{original_path}"
                                        )
                                    else:
                                        print(
                                            "[DND] No file content - original_path "
                                            f"not available or doesn't exist: "
                                            f"{original_path}"
                                        )
                            else:
                                print(
                                    f"[DND] Unexpected response type: "
                                    f"{data.get('type')}"
                                )

                    except Exception as e:
                        print(f"[DND] Websocket error during pre-fetch: {e}")
                        traceback.print_exc()

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(get_file())
                finally:
                    loop.close()

            except Exception as e:
                print(f"[DND] Failed to pre-fetch file: {e}")
                traceback.print_exc()

        # Run in background thread to avoid blocking UI
        thread = threading.Thread(target=fetch_and_save, daemon=True)
        thread.start()

    def _show_save_dialog(self):
        """Show file save dialog."""
        item_type = self.item["type"]
        self.item["id"]

        # Create file chooser dialog
        dialog = Gtk.FileDialog()

        # Set default filename based on type
        custom_name = self.item.get("name")
        if item_type == "text" or item_type == "url":
            filename = (
                f"{custom_name}.txt"
                if custom_name and not custom_name.endswith(".txt")
                else custom_name
                or ("url.txt" if item_type == "url" else "clipboard.txt")
            )
            dialog.set_initial_name(filename)
        elif item_type.startswith("image/"):
            ext = item_type.split("/")[-1]
            filename = (
                f"{custom_name}.{ext}"
                if custom_name and not custom_name.endswith(f".{ext}")
                else custom_name or f"clipboard.{ext}"
            )
            dialog.set_initial_name(filename)
        elif item_type == "screenshot":
            filename = (
                f"{custom_name}.png"
                if custom_name and not custom_name.endswith(".png")
                else custom_name or "screenshot.png"
            )
            dialog.set_initial_name(filename)

        window = self.get_root()

        def on_save_finish(dialog_obj, result):
            try:
                file = dialog_obj.save_finish(result)
                if file:
                    path = file.get_path()
                    if item_type == "text" or item_type == "url":
                        with open(path, "w") as f:
                            f.write(self.item["content"])
                        logger.info(
                            f"Saved {'URL' if item_type == 'url' else 'text'} to {path}"
                        )
                    elif (
                        item_type.startswith("image/")
                        or item_type == "screenshot"
                    ):
                        # Save image from base64 data
                        image_data = base64.b64decode(self.item["content"])
                        with open(path, "wb") as f:
                            f.write(image_data)
                        logger.info(f"Saved image to {path}")
            except Exception as e:
                logger.error(f"Error saving file: {e}")

        dialog.save(window, None, on_save_finish)

    def _show_view_dialog(self):
        """Show full item view dialog."""
        item_type = self.item["type"]
        window = self.get_root()

        dialog = Adw.Window(modal=True, transient_for=window)
        dialog.set_title("Full Clipboard Item")
        dialog.set_default_size(800, 600)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        main_box.set_margin_start(18)
        main_box.set_margin_end(18)
        main_box.set_margin_top(12)
        main_box.set_margin_bottom(12)

        # Header with close button
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        header_box.set_hexpand(True)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        header_box.append(spacer)

        close_button = Gtk.Button()
        close_button.set_icon_name("window-close-symbolic")
        close_button.set_tooltip_text("Close")
        close_button.connect("clicked", lambda btn: dialog.close())
        header_box.append(close_button)

        main_box.append(header_box)

        # Content area
        content_scroll = Gtk.ScrolledWindow()
        content_scroll.set_vexpand(True)
        content_scroll.set_hexpand(True)

        if item_type == "text" or item_type == "url":
            content_label = Gtk.Label(label=self.item["content"])
            content_label.set_wrap(True)
            content_label.set_selectable(True)
            content_label.set_halign(Gtk.Align.START)
            content_label.set_valign(Gtk.Align.START)
            content_scroll.set_child(content_label)

        elif item_type.startswith("image/") or item_type == "screenshot":
            image_data = base64.b64decode(self.item["content"])
            loader = GdkPixbuf.PixbufLoader()
            loader.write(image_data)
            loader.close()
            pixbuf = loader.get_pixbuf()
            texture = Gdk.Texture.new_for_pixbuf(pixbuf)

            picture = Gtk.Picture.new_for_paintable(texture)
            picture.set_halign(Gtk.Align.CENTER)
            picture.set_valign(Gtk.Align.CENTER)
            picture.set_content_fit(Gtk.ContentFit.CONTAIN)
            content_scroll.set_child(picture)

        elif item_type == "file":
            file_metadata = self.item.get("content", {})
            is_directory = file_metadata.get("is_directory", False)
            original_path = file_metadata.get("original_path", "")

            if is_directory and original_path and Path(original_path).exists():
                # Show folder contents with FileChooserWidget
                folder_box = Gtk.Box(
                    orientation=Gtk.Orientation.VERTICAL, spacing=12
                )

                # Info label
                info_label = Gtk.Label()
                folder_name = file_metadata.get("name", "Folder")
                info_label.set_markup(
                    f"<b>Folder:</b> {GLib.markup_escape_text(folder_name)}"
                )
                info_label.set_halign(Gtk.Align.START)
                folder_box.append(info_label)

                # Path label
                path_label = Gtk.Label(label=original_path)
                path_label.add_css_class("caption")
                path_label.add_css_class("dim-label")
                path_label.set_halign(Gtk.Align.START)
                path_label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
                folder_box.append(path_label)

                # FileChooserWidget to show folder tree
                file_chooser = Gtk.FileChooserWidget(
                    action=Gtk.FileChooserAction.OPEN
                )
                file_chooser.set_current_folder(
                    Gio.File.new_for_path(original_path)
                )
                file_chooser.set_vexpand(True)
                file_chooser.set_hexpand(True)

                folder_box.append(file_chooser)
                content_scroll.set_child(folder_box)
            else:
                # Regular file or folder doesn't exist
                file_info_box = Gtk.Box(
                    orientation=Gtk.Orientation.VERTICAL, spacing=12
                )
                file_info_box.set_valign(Gtk.Align.CENTER)
                file_info_box.set_halign(Gtk.Align.CENTER)

                file_name = file_metadata.get("name", "Unknown file")
                name_label = Gtk.Label()
                name_label.set_markup(
                    f"<b>{GLib.markup_escape_text(file_name)}</b>"
                )
                file_info_box.append(name_label)

                if original_path:
                    if not Path(original_path).exists():
                        error_label = Gtk.Label(
                            label="File/folder no longer exists at original location"
                        )
                        error_label.add_css_class("dim-label")
                        file_info_box.append(error_label)

                    path_label = Gtk.Label(label=original_path)
                    path_label.add_css_class("caption")
                    path_label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
                    path_label.set_max_width_chars(50)
                    file_info_box.append(path_label)

                # File metadata details
                details_box = Gtk.Box(
                    orientation=Gtk.Orientation.VERTICAL, spacing=6
                )
                details_box.set_margin_top(12)

                file_size = file_metadata.get("size", 0)
                if file_size > 0:
                    size_mb = file_size / (1024 * 1024)
                    size_label = Gtk.Label(label=f"Size: {size_mb:.2f} MB")
                    size_label.add_css_class("caption")
                    details_box.append(size_label)

                mime_type = file_metadata.get("mime_type", "")
                if mime_type:
                    type_label = Gtk.Label(label=f"Type: {mime_type}")
                    type_label.add_css_class("caption")
                    details_box.append(type_label)

                file_info_box.append(details_box)
                content_scroll.set_child(file_info_box)

        main_box.append(content_scroll)
        dialog.set_content(main_box)
        dialog.present()
