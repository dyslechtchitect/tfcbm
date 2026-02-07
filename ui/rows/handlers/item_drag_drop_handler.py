"""ItemDragDropHandler - Handles drag-and-drop operations for clipboard items.

This handler manages:
- Preparing drag content (text, images, files)
- Drag begin visual feedback
- File pre-fetching for drag-and-drop
"""

import asyncio
import base64
import json
import logging
import os
import tempfile
import threading
import traceback

from ui.services.ipc_helpers import connect as ipc_connect
from gi.repository import Gdk, GdkPixbuf, Gio, GLib, GObject, Gtk

logger = logging.getLogger("TFCBM.UI")


class ItemDragDropHandler:
    """Handles drag-and-drop operations for clipboard items."""

    def __init__(
        self,
        item: dict,
        card_frame,
        ws_service,
        on_show_auth_required: callable,
        on_show_fetch_error: callable,
    ):
        """Initialize the drag-and-drop handler.

        Args:
            item: The clipboard item data dictionary
            card_frame: The card widget used for drag icon
            ipc_service: ItemIPCService for server communication
            on_show_auth_required: Callback to show auth required notification
            on_show_fetch_error: Callback to show fetch error notification
        """
        self.item = item
        self.card_frame = card_frame
        self.ipc_service = ws_service
        self.on_show_auth_required = on_show_auth_required
        self.on_show_fetch_error = on_show_fetch_error
        self._file_temp_path = None

    def on_drag_prepare(self, drag_source, x, y):
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

    def on_drag_begin(self, drag_source, drag):
        """Called when drag begins - set drag icon."""
        print("[DND] _on_drag_begin called")
        # Use a small preview of the item as drag icon
        icon = Gtk.WidgetPaintable.new(self.card_frame)
        drag_source.set_icon(icon, 0, 0)
        print("[DND] Drag icon set")

    def prefetch_file_for_dnd(self):
        """Pre-fetch file content and save to temp location for drag-and-drop."""

        def fetch_and_save():
            print("[DND] Background thread started for pre-fetch")
            try:

                async def get_file():
                    item_id = self.item.get("id")
                    print(f"[DND] Async get_file() started for item {item_id}")

                    print(f"[DND] Pre-fetching file for item {item_id}")

                    try:
                        async with ipc_connect() as conn:
                            # Use same action as Save button: get_full_image
                            request = {
                                "action": "get_full_image",
                                "id": item_id,
                            }
                            await conn.send(json.dumps(request))

                            # Wait for response
                            response = await conn.recv()
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
