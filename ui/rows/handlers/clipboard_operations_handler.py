"""ClipboardOperationsHandler - Handles all clipboard copy and paste operations.

This handler manages:
- Copying text, images, and files to clipboard
- Secret authentication for copy operations
- Paste simulation
- Fetching full content from server for images and files
"""

import asyncio
import base64
import json
import logging
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

import websockets
from gi.repository import Gdk, GdkPixbuf, Gio, GLib

logger = logging.getLogger("TFCBM.UI")


class ClipboardOperationsHandler:
    """Handles clipboard operations for copying and pasting items."""

    def __init__(
        self,
        item: dict,
        window,
        ws_service,
        password_service,
        clipboard_service,
    ):
        """Initialize the clipboard operations handler.

        Args:
            item: The clipboard item data dictionary
            window: The window instance for notifications
            ws_service: ItemWebSocketService for server communication
            password_service: PasswordService for authentication
            clipboard_service: ClipboardService for clipboard operations
        """
        self.item = item
        self.window = window
        self.ws_service = ws_service
        self.password_service = password_service
        self.clipboard_service = clipboard_service

    def simulate_paste(self):
        """Simulate Ctrl+V paste after window is hidden."""
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

    def handle_copy_action(self):
        """Handle copy button click."""
        self.perform_copy_to_clipboard(
            self.item["type"], self.item["id"], self.item["content"]
        )

    def perform_copy_to_clipboard(self, item_type, item_id, content=None):
        """Copy item to clipboard.

        Args:
            item_type: Type of the item (text, url, image, file)
            item_id: ID of the item
            content: Content to copy (optional, fetched if secret)
        """
        # Check if item is secret and require authentication
        is_secret = self.item.get("is_secret", False)
        if is_secret:
            logger.info(f"Item {item_id} is secret, checking authentication")
            # Check if authenticated for THIS specific copy operation on THIS item
            if not self.password_service.is_authenticated_for("copy", item_id):
                logger.info("Not authenticated for copy operation, prompting for password")
                # Prompt for authentication for THIS operation on THIS item
                # Note: we need the root widget, which we'll get from a callback
                if not self.password_service.authenticate_for("copy", item_id, None):
                    logger.info("Authentication failed or cancelled")
                    self.window.show_notification("Authentication required to copy secret")
                    return
                else:
                    logger.info("Authentication successful for copy operation")
            else:
                logger.info("Already authenticated for copy operation")

            # For secrets, we need to fetch the actual content from the server
            # (not the "-secret-" placeholder)
            logger.info(f"Fetching real content for secret item {item_id}")
            content = self.ws_service.fetch_secret_content(item_id)
            if not content:
                self.window.show_notification("Failed to retrieve secret content")
                # Consume authentication even on failure
                self.password_service.consume_authentication("copy", item_id)
                return
            logger.info(f"Retrieved secret content (length: {len(str(content))})")

        clipboard = Gdk.Display.get_default().get_clipboard()
        if not clipboard:
            self.window.show_notification("Error: Could not access clipboard.")
            # Consume authentication even on error
            if is_secret:
                self.password_service.consume_authentication("copy", item_id)
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
                    self.ws_service.record_paste(item_id)
                    # Consume authentication after successful copy
                    if is_secret:
                        self.password_service.consume_authentication("copy", item_id)
                else:
                    self.window.show_notification(
                        "Error copying: content is empty."
                    )
                    # Consume authentication even on error
                    if is_secret:
                        self.password_service.consume_authentication("copy", item_id)
            elif item_type == "file":
                self.window.show_notification("Loading file...")
                self._copy_file_to_clipboard(item_id, content, clipboard)
            elif item_type.startswith("image/") or item_type == "screenshot":
                self.window.show_notification("Loading full image...")
                self._copy_full_image_to_clipboard(item_id, clipboard)
        except Exception as e:
            self.window.show_notification(f"Error copying: {str(e)}")
            # Consume authentication even on error
            if is_secret:
                self.password_service.consume_authentication("copy", item_id)

    def _copy_full_image_to_clipboard(self, item_id, clipboard):
        """Fetch and copy full image to clipboard.

        Args:
            item_id: ID of the image item
            clipboard: Clipboard instance
        """

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
                                    self.ws_service.record_paste(item_id)
                                    # Consume authentication after successful copy
                                    if self.item.get("is_secret", False):
                                        self.password_service.consume_authentication("copy", item_id)
                                except Exception as e:
                                    self.window.show_notification(
                                        f"Error copying: {str(e)}"
                                    )
                                return False

                            GLib.idle_add(copy_to_clipboard)

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(get_full_image())
                finally:
                    loop.close()

            except Exception as e:
                GLib.idle_add(
                    lambda: self.window.show_notification(f"Error: {str(e)}")
                    or False
                )

        threading.Thread(target=fetch_and_copy, daemon=True).start()

    def _copy_file_to_clipboard(self, item_id, file_metadata, clipboard):
        """Copy file or folder to clipboard.

        Args:
            item_id: ID of the file item
            file_metadata: File metadata dictionary
            clipboard: Clipboard instance
        """
        is_directory = file_metadata.get("is_directory", False)

        if is_directory:
            self._copy_folder_to_clipboard(item_id, file_metadata, clipboard)
        else:
            self._copy_regular_file_to_clipboard(
                item_id, file_metadata, clipboard
            )

    def _copy_folder_to_clipboard(self, item_id, file_metadata, clipboard):
        """Copy folder to clipboard if it still exists.

        Args:
            item_id: ID of the folder item
            file_metadata: Folder metadata dictionary
            clipboard: Clipboard instance
        """

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
                            self.ws_service.record_paste(item_id)
                            # Consume authentication after successful copy
                            if self.item.get("is_secret", False):
                                self.password_service.consume_authentication("copy", item_id)
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
            except Exception as e:
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
        """Fetch file from server and copy to clipboard.

        Args:
            item_id: ID of the file item
            file_metadata: File metadata dictionary
            clipboard: Clipboard instance
        """

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
                                    self.ws_service.record_paste(item_id)
                                    # Consume authentication after successful copy
                                    if self.item.get("is_secret", False):
                                        self.password_service.consume_authentication("copy", item_id)
                                except Exception as e:
                                    self.window.show_notification(
                                        f"Error copying file: {str(e)}"
                                    )
                                return False

                            GLib.idle_add(copy_to_clipboard)

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(get_full_file())
                finally:
                    loop.close()

            except Exception as e:
                GLib.idle_add(
                    lambda: self.window.show_notification(
                        f"Error copying file: {str(e)}"
                    )
                    or False
                )

        threading.Thread(target=fetch_and_copy, daemon=True).start()
