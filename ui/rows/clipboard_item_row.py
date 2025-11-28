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

from gi.repository import Adw, Gdk, GdkPixbuf, Gio, GLib, GObject, Gtk

from ui.components.items import ItemActions, ItemContent, ItemHeader, ItemTags

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

        item_height = self.window.settings.item_height

        self.set_activatable(True)
        self.connect("activate", lambda row: self._on_row_clicked(self))

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        main_box.set_hexpand(True)
        main_box.set_vexpand(False)
        main_box.set_size_request(-1, item_height)
        main_box.set_margin_start(12)
        main_box.set_margin_end(12)
        main_box.set_margin_top(8)
        main_box.set_margin_bottom(8)
        main_box.set_valign(Gtk.Align.FILL)
        main_box.set_overflow(Gtk.Overflow.HIDDEN)

        card_frame = Gtk.Frame()
        card_frame.set_vexpand(False)
        card_frame.set_hexpand(True)
        card_frame.set_size_request(-1, item_height)
        card_frame.add_css_class("clipboard-item-card")
        card_frame.set_child(main_box)
        self.card_frame = card_frame

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

        header = ItemHeader(
            item=self.item,
            on_name_save=self._update_item_name,
            show_pasted_time=self.show_pasted_time,
            search_query=self.search_query,
        )
        main_box.append(header.build())

        content = ItemContent(item=self.item, search_query=self.search_query)
        main_box.append(content.build())

        actions = ItemActions(
            item=self.item,
            on_copy=self._on_copy_action,
            on_view=self._on_view_action,
            on_save=self._on_save_action,
            on_tags=self._on_tags_action,
            on_delete=self._on_delete_action,
        )
        main_box.append(actions.build())

        overlay = Gtk.Overlay()
        overlay.set_child(card_frame)

        tags = ItemTags(
            tags=self.item.get("tags", []), on_click=self._on_tags_action
        )
        overlay.add_overlay(tags.build())

        self.set_child(overlay)

    def _on_row_clicked(self, row):
        """Copy item to clipboard when row is clicked."""
        self._perform_copy_to_clipboard(
            self.item["type"], self.item["id"], self.item["content"]
        )

    def _on_copy_action(self):
        """Handle copy button click."""
        self._perform_copy_to_clipboard(
            self.item["type"], self.item["id"], self.item["content"]
        )

    def _on_view_action(self):
        """Handle view button click."""
        print(f"[UI] View item {self.item['id']}")

    def _on_save_action(self):
        """Handle save button click."""
        print(f"[UI] Save item {self.item['id']}")

    def _on_tags_action(self):
        """Handle tags button click - show tags popover."""
        self._show_tags_popover()

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
            if item_type == "text":
                if content:
                    clipboard.set(content)
                    self.window.show_notification("Text copied to clipboard")
                    self._record_paste(item_id)
                else:
                    self.window.show_notification(
                        "Error copying text: content is empty."
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

        def update():
            try:

                async def send_update():
                    uri = "ws://localhost:8765"
                    async with websockets.connect(uri) as websocket:
                        request = {
                            "action": "update_item_name",
                            "id": item_id,
                            "name": name,
                        }
                        await websocket.send(json.dumps(request))
                        await websocket.recv()

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(send_update())
            except Exception as e:
                print(f"Error updating name: {e}")

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
        """Show tags management popover - delegate to window."""
        # Window has all tags list, handles this
        if hasattr(self.window, "_show_tags_popover_for_item"):
            self.window._show_tags_popover_for_item(self.item)

    def _on_tag_drop(self, drop_target, value, x, y):
        """Handle tag drop on item."""
        tag_id = value
        item_id = self.item.get("id")
        if hasattr(self.window, "_on_tag_dropped_on_item"):
            self.window._on_tag_dropped_on_item(tag_id, item_id)
        return True

    def _on_card_clicked(self, gesture, n_press, x, y):
        """Handle card click."""
        # Single click handled by row activation

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
