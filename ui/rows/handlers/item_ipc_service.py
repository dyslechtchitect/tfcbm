"""ItemIPCService - Handles all IPC communication with the server.

This service manages:
- Secret content fetching
- Secret status toggling
- Tag loading
- Paste recording
- Item name updates
- Item deletion
"""

import asyncio
import json
import logging
import threading
import time
from typing import Callable, Optional

from ui.services.ipc_helpers import connect as ipc_connect
from gi.repository import GLib

logger = logging.getLogger("TFCBM.UI")


class ItemIPCService:
    """Handles IPC communication for clipboard item operations."""

    def __init__(
        self,
        item: dict,
        window,
        on_rebuild_content: Callable[[], None],
        on_update_lock_button: Callable[[], None],
        on_display_tags: Callable[[list], None],
        on_update_header_name: Callable[[], None] = None,
    ):
        """Initialize the IPC service.

        Args:
            item: The clipboard item data dictionary
            window: The window instance for notifications
            on_rebuild_content: Callback to rebuild item content display
            on_update_lock_button: Callback to update lock button icon
            on_display_tags: Callback to display tags in UI
            on_update_header_name: Callback to update the name in the header
        """
        self.item = item
        self.window = window
        self.on_rebuild_content = on_rebuild_content
        self.on_update_lock_button = on_update_lock_button
        self.on_display_tags = on_display_tags
        self.on_update_header_name = on_update_header_name
        self._last_paste_time = 0

    def fetch_secret_content(self, item_id: int) -> Optional[str]:
        """Fetch the actual content of a secret item from the server.

        Args:
            item_id: ID of the secret item

        Returns:
            The secret content string, or None if fetch failed
        """
        content = [None]  # Use list to allow modification in nested function

        def fetch_content():
            try:

                async def get_content():
                    async with ipc_connect() as conn:
                        request = {"action": "get_item", "item_id": item_id}
                        await conn.send(json.dumps(request))
                        response = await conn.recv()
                        data = json.loads(response)

                        if data.get("type") == "item" and data.get("item"):
                            item_data = data["item"]
                            content[0] = item_data.get("content")
                            logger.info(f"Fetched secret content for item {item_id}")

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(get_content())
                finally:
                    loop.close()

            except Exception as e:
                logger.error(f"Error fetching secret content: {e}")

        # Run synchronously in a thread and wait
        thread = threading.Thread(target=fetch_content)
        thread.start()
        thread.join(timeout=5)  # Wait up to 5 seconds

        return content[0]

    def toggle_secret_status(
        self, item_id: int, is_secret: bool, name: Optional[str] = None
    ) -> None:
        """Send request to server to toggle secret status.

        Args:
            item_id: ID of the item
            is_secret: Whether to mark as secret (True) or unmark (False)
            name: Optional name for the secret item
        """
        logger.info(
            f"toggle_secret_status called: item_id={item_id}, is_secret={is_secret}, name='{name}'"
        )

        def send_toggle():
            try:

                async def toggle_secret():
                    async with ipc_connect() as conn:
                        request = {
                            "action": "toggle_secret",
                            "item_id": item_id,
                            "is_secret": is_secret,
                            "name": name,
                        }
                        await conn.send(json.dumps(request))
                        response = await conn.recv()
                        data = json.loads(response)
                        logger.info(f"Received response: {data}")

                        if data.get("type") == "secret_toggled":
                            if data.get("success"):
                                # Update local item data from server response
                                received_is_secret = data.get("is_secret", is_secret)
                                logger.info(
                                    f"Received is_secret from server: {received_is_secret} (type: {type(received_is_secret)})"
                                )

                                # Ensure boolean conversion (SQLite returns 0/1 as integers)
                                self.item["is_secret"] = bool(received_is_secret)

                                server_name = data.get("name")
                                if server_name:
                                    self.item["name"] = server_name
                                    logger.info(f"Updated item name to: {server_name}")

                                    # Update the name in the header
                                    if self.on_update_header_name:
                                        logger.info("Calling on_update_header_name via GLib.idle_add")
                                        GLib.idle_add(self.on_update_header_name)

                                logger.info(
                                    f"Item {item_id} secret status updated: is_secret={self.item['is_secret']} (bool), name={self.item.get('name')}"
                                )

                                # Immediately rebuild content to show/hide secret
                                logger.info("Calling on_rebuild_content via GLib.idle_add")
                                GLib.idle_add(self.on_rebuild_content)

                                # Update lock button icon
                                logger.info(
                                    "Calling on_update_lock_button via GLib.idle_add"
                                )
                                GLib.idle_add(self.on_update_lock_button)

                                # Show notification
                                status = (
                                    "marked as secret" if is_secret else "unmarked as secret"
                                )
                                GLib.idle_add(
                                    self.window.show_notification,
                                    f"Item {status}",
                                )
                            else:
                                error_msg = data.get("error", "Unknown error")
                                logger.error(
                                    f"Failed to toggle secret status: {error_msg}"
                                )
                                GLib.idle_add(
                                    self.window.show_notification,
                                    f"Failed to update: {error_msg}",
                                )

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(toggle_secret())
                finally:
                    loop.close()
            except Exception as e:
                logger.error(f"Error toggling secret status: {e}")
                GLib.idle_add(
                    self.window.show_notification,
                    f"Error: {str(e)}",
                )

        threading.Thread(target=send_toggle, daemon=True).start()

    def toggle_favorite(self, item_id: int, is_favorite: bool) -> None:
        """Send request to server to toggle favorite status.

        Args:
            item_id: ID of the item
            is_favorite: Whether to mark as favorite (True) or unmark (False)
        """
        logger.info(f"toggle_favorite called: item_id={item_id}, is_favorite={is_favorite}")

        def send_toggle():
            try:

                async def toggle_fav():
                    async with ipc_connect() as conn:
                        request = {
                            "action": "toggle_favorite",
                            "item_id": item_id,
                            "is_favorite": is_favorite,
                        }
                        await conn.send(json.dumps(request))
                        response = await conn.recv()
                        data = json.loads(response)
                        logger.info(f"Received response: {data}")

                        if data.get("type") == "favorite_toggled":
                            if data.get("success"):
                                # Update local item data
                                self.item["is_favorite"] = bool(is_favorite)
                                logger.info(f"Item {item_id} favorite status updated: is_favorite={is_favorite}")
                            else:
                                error_msg = data.get("error", "Unknown error")
                                logger.error(f"Failed to toggle favorite status: {error_msg}")
                                GLib.idle_add(
                                    self.window.show_notification,
                                    f"Failed to update favorite: {error_msg}",
                                )

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(toggle_fav())
                finally:
                    loop.close()
            except Exception as e:
                logger.error(f"Error toggling favorite status: {e}")
                GLib.idle_add(
                    self.window.show_notification,
                    f"Error: {str(e)}",
                )

        threading.Thread(target=send_toggle, daemon=True).start()

    def load_item_tags(self) -> None:
        """Load and display tags for this item asynchronously."""

        def run_load():
            try:

                async def fetch_tags():
                    async with ipc_connect() as conn:
                        request = {
                            "action": "get_item_tags",
                            "item_id": self.item.get("id"),
                        }
                        await conn.send(json.dumps(request))
                        response = await conn.recv()
                        data = json.loads(response)

                        if data.get("type") == "item_tags":
                            tags = data.get("tags", [])

                            # Filter out deleted tags by checking against window.all_tags
                            if hasattr(self.window, 'all_tags'):
                                valid_tag_ids = {tag.get('id') for tag in self.window.all_tags}
                                tags = [tag for tag in tags if tag.get('id') in valid_tag_ids]

                            # Store tags in item for filtering
                            self.item["tags"] = tags
                            # Update UI on main thread
                            GLib.idle_add(self.on_display_tags, tags)

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(fetch_tags())
                finally:
                    loop.close()
            except Exception as e:
                logger.error(f"[UI] Error loading item tags: {e}")

        threading.Thread(target=run_load, daemon=True).start()

    def record_paste(self, item_id: int) -> None:
        """Record that this item was pasted.

        Args:
            item_id: ID of the pasted item
        """
        current_time = time.time()
        if current_time - self._last_paste_time < 1.0:
            return

        self._last_paste_time = current_time

        def record():
            try:

                async def send_record():
                    async with ipc_connect() as conn:
                        request = {"action": "record_paste", "id": item_id}
                        await conn.send(json.dumps(request))
                        await conn.recv()

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(send_record())
                finally:
                    loop.close()
            except Exception as e:
                print(f"Error recording paste: {e}")

        threading.Thread(target=record, daemon=True).start()

    def update_item_name(self, item_id: int, name: str) -> None:
        """Update item name on server.

        Args:
            item_id: ID of the item
            name: New name for the item
        """
        # Update local item data immediately
        self.item["name"] = name

        def update():
            try:

                async def send_update():
                    async with ipc_connect() as conn:
                        request = {
                            "action": "update_item_name",
                            "item_id": item_id,
                            "name": name,
                        }
                        await conn.send(json.dumps(request))
                        response = await conn.recv()
                        data = json.loads(response)

                        if data.get("type") == "item_name_updated":
                            if data.get("success"):
                                logger.info(f"[UI] Name updated for item {item_id}: '{name}'")
                            else:
                                logger.error(
                                    f"[UI] Failed to update name for item {item_id}: {data.get('error', 'Unknown error')}"
                                )
                        else:
                            logger.warning(f"[UI] Unexpected response updating name: {data}")

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(send_update())
                finally:
                    loop.close()
            except Exception as e:
                logger.error(f"[UI] Error updating name: {e}")

        threading.Thread(target=update, daemon=True).start()

    def delete_item_from_server(self, item_id: int) -> None:
        """Send delete request to server via IPC.

        Args:
            item_id: ID of the item to delete
        """

        def send_delete():
            try:

                async def delete_item():
                    async with ipc_connect() as conn:
                        request = {"action": "delete_item", "id": item_id}
                        await conn.send(json.dumps(request))
                        response = await conn.recv()
                        data = json.loads(response)

                        if data.get("status") == "success":
                            GLib.idle_add(
                                lambda: self.window.show_notification("Item deleted") or False
                            )
                        else:
                            GLib.idle_add(
                                lambda: self.window.show_notification("Failed to delete item")
                                or False
                            )

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(delete_item())
                finally:
                    loop.close()
            except Exception as e:
                print(f"Error deleting item: {e}")
                GLib.idle_add(
                    lambda: self.window.show_notification(f"Error deleting: {str(e)}") or False
                )

        threading.Thread(target=send_delete, daemon=True).start()
