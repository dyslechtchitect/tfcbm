"""ItemIPCService - Handles all IPC communication with the server.

This service manages:
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
        on_display_tags: Callable[[list], None],
        on_update_header_name: Callable[[], None] = None,
    ):
        """Initialize the IPC service.

        Args:
            item: The clipboard item data dictionary
            window: The window instance for notifications
            on_rebuild_content: Callback to rebuild item content display
            on_display_tags: Callback to display tags in UI
            on_update_header_name: Callback to update the name in the header
        """
        self.item = item
        self.window = window
        self.on_rebuild_content = on_rebuild_content
        self.on_display_tags = on_display_tags
        self.on_update_header_name = on_update_header_name
        self._last_paste_time = 0

    def fetch_full_text(self, item_id: int) -> Optional[str]:
        """Fetch the full text content for a truncated text item.

        Args:
            item_id: ID of the text item

        Returns:
            The full text content string, or None if fetch failed
        """
        content = [None]  # Use list to allow modification in nested function

        def fetch_content():
            try:

                async def get_content():
                    async with ipc_connect() as conn:
                        request = {"action": "get_full_text", "id": item_id}
                        await conn.send(json.dumps(request))
                        response = await conn.recv()
                        data = json.loads(response)

                        if data.get("type") == "full_text" and data.get("content"):
                            content[0] = data["content"]
                            logger.info(f"Fetched full text for item {item_id} ({len(content[0])} chars)")

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(get_content())
                finally:
                    loop.close()

            except Exception as e:
                logger.error(f"Error fetching full text content: {e}")

        # Run synchronously in a thread and wait
        thread = threading.Thread(target=fetch_content)
        thread.start()
        thread.join(timeout=5)  # Wait up to 5 seconds

        return content[0]

    def fetch_text_page(self, item_id: int, page: int, page_size: int = 500) -> Optional[dict]:
        """Fetch a single page of text content from the server.

        Args:
            item_id: ID of the text item
            page: Page number (0-indexed)
            page_size: Characters per page

        Returns:
            Dict with content, page, total_pages, total_length or None if fetch failed
        """
        result = [None]

        def fetch_content():
            try:

                async def get_content():
                    async with ipc_connect() as conn:
                        request = {
                            "action": "get_text_page",
                            "id": item_id,
                            "page": page,
                            "page_size": page_size,
                        }
                        await conn.send(json.dumps(request))
                        response = await conn.recv()
                        data = json.loads(response)

                        if data.get("type") == "text_page":
                            result[0] = {
                                "content": data.get("content", ""),
                                "page": data.get("page", 0),
                                "total_pages": data.get("total_pages", 1),
                                "total_length": data.get("total_length", 0),
                            }
                            logger.info(
                                f"Fetched text page {page} for item {item_id} "
                                f"({len(result[0]['content'])} chars)"
                            )

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(get_content())
                finally:
                    loop.close()

            except Exception as e:
                logger.error(f"Error fetching text page: {e}")

        thread = threading.Thread(target=fetch_content)
        thread.start()
        thread.join(timeout=5)

        return result[0]

    def fetch_text_page_async(self, item_id: int, page: int, callback, page_size: int = 500):
        """Fetch a single page of text content asynchronously.

        Args:
            item_id: ID of the text item
            page: Page number (0-indexed)
            callback: Callback receiving the result dict (called on main thread)
            page_size: Characters per page
        """

        def fetch_content():
            try:

                async def get_content():
                    async with ipc_connect() as conn:
                        request = {
                            "action": "get_text_page",
                            "id": item_id,
                            "page": page,
                            "page_size": page_size,
                        }
                        await conn.send(json.dumps(request))
                        response = await conn.recv()
                        data = json.loads(response)

                        if data.get("type") == "text_page":
                            result = {
                                "content": data.get("content", ""),
                                "page": data.get("page", 0),
                                "total_pages": data.get("total_pages", 1),
                                "total_length": data.get("total_length", 0),
                            }
                            GLib.idle_add(callback, result)
                        else:
                            GLib.idle_add(callback, None)

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(get_content())
                finally:
                    loop.close()

            except Exception as e:
                logger.error(f"Error fetching text page async: {e}")
                GLib.idle_add(callback, None)

        threading.Thread(target=fetch_content, daemon=True).start()

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
