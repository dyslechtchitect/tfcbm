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
import tempfile
import threading
from pathlib import Path

from ui.services.ipc_helpers import connect as ipc_connect
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
            ipc_service: ItemIPCService for server communication
            password_service: PasswordService for authentication
            clipboard_service: ClipboardService for clipboard operations
        """
        self.item = item
        self.window = window
        self.ipc_service = ws_service
        self.password_service = password_service
        self.clipboard_service = clipboard_service
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

        Returns:
            bool: True if copy was successful, False otherwise
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
                if not self.password_service.authenticate_for("copy", item_id, self.window):
                    logger.info("Authentication failed or cancelled")
                    self.window.show_notification("Authentication required to copy protected item")
                    return False
                else:
                    logger.info("Authentication successful for copy operation")
            else:
                logger.info("Already authenticated for copy operation")

            # For secrets, we need to fetch the actual content from the server
            # (not the "-secret-" placeholder)
            logger.info(f"Fetching real content for secret item {item_id}")
            content = self.ipc_service.fetch_secret_content(item_id)
            if not content:
                self.window.show_notification("Failed to retrieve secret content")
                # Consume authentication even on failure
                self.password_service.consume_authentication("copy", item_id)
                return False
            logger.info(f"Retrieved secret content (length: {len(str(content))})")

        clipboard = Gdk.Display.get_default().get_clipboard()
        if not clipboard:
            self.window.show_notification("Error: Could not access clipboard.")
            # Consume authentication even on error
            if is_secret:
                self.password_service.consume_authentication("copy", item_id)
            return False

        try:
            if item_type == "text" or item_type == "url":
                if content:
                    # Check if content was truncated and fetch full text if needed
                    content_truncated = self.item.get("content_truncated", False)
                    if content_truncated:
                        logger.info(f"Content truncated for item {item_id}, fetching full text...")
                        full_content = self.ipc_service.fetch_full_text(item_id)
                        if full_content:
                            content = full_content
                            # Update item with full content for future use
                            self.item["content"] = full_content
                            self.item["content_truncated"] = False
                            logger.info(f"Retrieved full text ({len(content)} chars)")
                        else:
                            logger.warning(f"Failed to fetch full text for item {item_id}")
                            # Continue with truncated content as fallback

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
                    self.ipc_service.record_paste(item_id)
                    # Consume authentication after successful copy
                    if is_secret:
                        self.password_service.consume_authentication("copy", item_id)
                    return True
                else:
                    self.window.show_notification(
                        "Error copying: content is empty."
                    )
                    # Consume authentication even on error
                    if is_secret:
                        self.password_service.consume_authentication("copy", item_id)
                    return False
            elif item_type == "file":
                self.window.show_notification("Loading file...")
                self._copy_file_to_clipboard(item_id, content, clipboard)
                return True  # Async operation started successfully
            elif item_type.startswith("image/") or item_type == "screenshot":
                self.window.show_notification("Loading full image...")
                self._copy_full_image_to_clipboard(item_id, item_type, clipboard)
                return True  # Async operation started successfully
        except Exception as e:
            self.window.show_notification(f"Error copying: {str(e)}")
            # Consume authentication even on error
            if is_secret:
                self.password_service.consume_authentication("copy", item_id)
            return False

        return True  # Default success

    def _copy_full_image_to_clipboard(self, item_id, item_type, clipboard):
        """Fetch and copy full image to clipboard.

        Args:
            item_id: ID of the image item
            item_type: MIME type of the image (e.g., "image/png", "screenshot")
            clipboard: Clipboard instance
        """

        def fetch_and_copy():
            try:

                async def get_full_image():
                    async with ipc_connect() as conn:
                        request = {"action": "get_full_image", "id": item_id}
                        await conn.send(json.dumps(request))

                        response = await conn.recv()
                        data = json.loads(response)

                        if (
                            data.get("type") == "full_image"
                            and data.get("id") == item_id
                        ):
                            image_b64 = data.get("content")
                            image_data = base64.b64decode(image_b64)

                            def copy_to_clipboard():
                                try:
                                    # Copy original bytes directly without re-encoding
                                    # This preserves the hash so duplicates are detected
                                    mime_type = item_type if item_type.startswith("image/") else "image/png"

                                    gbytes = GLib.Bytes.new(image_data)
                                    content = (
                                        Gdk.ContentProvider.new_for_bytes(
                                            mime_type, gbytes
                                        )
                                    )
                                    clipboard.set_content(content)

                                    # Calculate size in KB
                                    size_kb = len(image_data) / 1024
                                    self.window.show_notification(
                                        f"📷 Image copied ({size_kb:.1f} KB)"
                                    )
                                    self.ipc_service.record_paste(item_id)
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
                            self.ipc_service.record_paste(item_id)
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
                    async with ipc_connect() as conn:
                        request = {"action": "get_full_image", "id": item_id}
                        await conn.send(json.dumps(request))

                        response = await conn.recv()
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
                                    self.ipc_service.record_paste(item_id)
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
