#!/usr/bin/env python3
"""
IPC Service - Handles UNIX domain socket communication with UI
Replaces WebSocket for local inter-process communication
"""
import asyncio
import base64
import json
import logging
import os
import traceback
from typing import Set, Optional, Tuple

from server.src.services.thumbnail_service import ThumbnailService

logger = logging.getLogger(__name__)


class IPCConnection:
    """Represents a single IPC client connection."""

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        self.closed = False

    async def send_json(self, data: dict):
        """Send a JSON message to the client with length prefix."""
        if self.closed or self.writer.is_closing():
            return

        try:
            json_str = json.dumps(data)
            message_bytes = json_str.encode('utf-8') + b'\n'
            # Send length prefix followed by message
            length_prefix = f"{len(message_bytes)}\n".encode('utf-8')
            self.writer.write(length_prefix + message_bytes)
            await self.writer.drain()
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            self.closed = True

    async def receive_json(self) -> Optional[dict]:
        """Receive a JSON message from the client with length prefix."""
        if self.closed:
            return None

        try:
            # Read length prefix
            length_line = await self.reader.readuntil(b'\n')
            message_length = int(length_line.decode('utf-8').strip())

            # Read message
            message_bytes = await self.reader.readexactly(message_length)
            message_str = message_bytes.decode('utf-8').rstrip('\n')
            return json.loads(message_str)
        except asyncio.IncompleteReadError:
            # Connection closed
            self.closed = True
            return None
        except Exception as e:
            logger.error(f"Error receiving message: {e}")
            self.closed = True
            return None

    async def close(self):
        """Close the connection."""
        if not self.closed:
            self.closed = True
            self.writer.close()
            await self.writer.wait_closed()


class IPCService:
    """Service for UNIX domain socket communication with UI clients"""

    def __init__(self, database_service, settings_service, clipboard_service):
        """
        Initialize IPC service

        Args:
            database_service: Database service
            settings_service: Settings service
            clipboard_service: Clipboard service
        """
        logger.info("[IPCService.__init__] Starting initialization...")
        self.db_service = database_service
        self.settings_service = settings_service
        self.clipboard_service = clipboard_service
        self.clients: Set[IPCConnection] = set()
        self.ui_pid: Optional[int] = None
        self.last_known_id = database_service.get_latest_id() or 0
        self.socket_path = self._get_socket_path()
        logger.info("[IPCService.__init__] Initialization complete")

    def _get_socket_path(self) -> str:
        """Get the UNIX socket path in XDG_RUNTIME_DIR."""
        runtime_dir = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
        return os.path.join(runtime_dir, "tfcbm-ipc.sock")

    def prepare_item_for_ui(self, item: dict) -> dict:
        """Convert database item to UI-renderable format"""
        item_type = item["type"]
        data = item["data"]
        thumbnail = item.get("thumbnail")

        if item_type == "text" or item_type == "url":
            content = data.decode("utf-8") if isinstance(data, bytes) else data
            thumbnail_b64 = None
        elif item_type == "file":
            try:
                separator = b'\n---FILE_CONTENT---\n'
                if separator in data:
                    metadata_bytes, _ = data.split(separator, 1)
                    metadata_json = metadata_bytes.decode('utf-8')
                    metadata = json.loads(metadata_json)
                    content = metadata
                else:
                    content = {"error": "Invalid file data format"}
                thumbnail_b64 = None
            except Exception as e:
                logger.error(f"Error parsing file metadata for item {item['id']}: {e}")
                content = {"error": "Failed to parse file metadata"}
                thumbnail_b64 = None
        elif item_type.startswith("image/") or item_type == "screenshot":
            content = None
            if thumbnail:
                thumbnail_b64 = base64.b64encode(thumbnail).decode("utf-8")
                if len(thumbnail_b64) > 500 * 1024:
                    logger.warning(f"Thumbnail for item {item['id']} is too large, sending None.")
                    thumbnail_b64 = None
            else:
                thumb_service = ThumbnailService(self.db_service)
                thumb = thumb_service.generate_thumbnail(data, max_size=250)
                if thumb:
                    thumbnail_b64 = base64.b64encode(thumb).decode("utf-8")
                    if len(thumbnail_b64) <= 500 * 1024:
                        self.db_service.update_thumbnail(item["id"], thumb)
                    else:
                        thumbnail_b64 = None
                else:
                    thumbnail_b64 = None
        else:
            content = None
            thumbnail_b64 = None

        return {
            "id": item["id"],
            "type": item_type,
            "content": content,
            "thumbnail": thumbnail_b64,
            "timestamp": item["timestamp"],
            "name": item.get("name"),
            "format_type": item.get("format_type"),
            "formatted_content": base64.b64encode(item["formatted_content"]).decode("utf-8") if item.get("formatted_content") else None,
            "is_secret": item.get("is_secret", False),
            "is_favorite": item.get("is_favorite", False),
        }

    async def client_handler(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle IPC client connections"""
        addr = writer.get_extra_info('peername', 'unknown')
        logger.info(f"IPC client connected from {addr}")

        connection = IPCConnection(reader, writer)
        self.clients.add(connection)

        try:
            while not connection.closed:
                message = await connection.receive_json()
                if message is None:
                    break

                try:
                    await self._handle_message(connection, message)
                except Exception as e:
                    logger.error(f"Error handling IPC message: {e}")
                    traceback.print_exc()

        except Exception as e:
            logger.error(f"IPC handler error: {e}")
            traceback.print_exc()
        finally:
            self.clients.discard(connection)
            await connection.close()
            logger.info("IPC client disconnected")

    async def _handle_message(self, connection: IPCConnection, data: dict):
        """Handle individual IPC message"""
        action = data.get("action")

        if action == "get_history":
            await self._handle_get_history(connection, data)
        elif action == "register_ui_pid":
            await self._handle_register_ui_pid(connection, data)
        elif action == "get_full_image":
            await self._handle_get_full_image(connection, data)
        elif action == "delete_item":
            await self._handle_delete_item(connection, data)
        elif action == "get_recently_pasted":
            await self._handle_get_recently_pasted(connection, data)
        elif action == "record_paste":
            await self._handle_record_paste(connection, data)
        elif action == "search":
            await self._handle_search(connection, data)
        elif action == "get_tags":
            await self._handle_get_tags(connection)
        elif action == "create_tag":
            await self._handle_create_tag(connection, data)
        elif action == "update_tag":
            await self._handle_update_tag(connection, data)
        elif action == "delete_tag":
            await self._handle_delete_tag(connection, data)
        elif action == "add_item_tag" or action == "add_tag":
            await self._handle_add_tag(connection, data)
        elif action == "remove_item_tag" or action == "remove_tag":
            await self._handle_remove_tag(connection, data)
        elif action == "get_item_tags":
            await self._handle_get_item_tags(connection, data)
        elif action == "get_items_by_tags":
            await self._handle_get_items_by_tags(connection, data)
        elif action == "update_item_name":
            await self._handle_update_item_name(connection, data)
        elif action == "toggle_secret":
            await self._handle_toggle_secret(connection, data)
        elif action == "toggle_favorite":
            await self._handle_toggle_favorite(connection, data)
        elif action == "get_item":
            await self._handle_get_item(connection, data)
        elif action == "get_file_extensions":
            await self._handle_get_file_extensions(connection)
        elif action == "get_total_count":
            await self._handle_get_total_count(connection)
        elif action == "update_retention_settings":
            await self._handle_update_retention_settings(connection, data)
        elif action == "update_clipboard_settings":
            await self._handle_update_clipboard_settings(connection, data)
        elif action == "clipboard_event":
            await self._handle_clipboard_event(data)
        elif action == "shutdown":
            await self._handle_shutdown(connection)
        else:
            logger.warning(f"Unknown IPC action: {action}")

    async def _handle_get_history(self, connection: IPCConnection, data):
        """Handle get_history action"""
        limit = data.get("limit", self.settings_service.max_page_length)
        offset = data.get("offset", 0)
        sort_order = data.get("sort_order", "DESC")
        filters = data.get("filters", None)

        logger.info(f"[FILTER] get_history request with filters: {filters}")

        items = self.db_service.get_items(limit=limit, offset=offset, sort_order=sort_order, filters=filters)
        total_count = self.db_service.get_total_count()
        logger.info(f"[FILTER] Returned {len(items)} items (total: {total_count})")

        ui_items = [self.prepare_item_for_ui(item) for item in items]

        response = {"type": "history", "items": ui_items, "total_count": total_count, "offset": offset}
        await connection.send_json(response)

    async def _handle_register_ui_pid(self, connection: IPCConnection, data):
        """Handle register_ui_pid action"""
        pid = data.get("pid")
        if pid:
            self.ui_pid = pid
            logger.info(f"Registered UI PID: {self.ui_pid}")
            response = {"type": "ui_pid_registered", "success": True}
        else:
            response = {"type": "ui_pid_registered", "success": False, "error": "pid is required"}
        await connection.send_json(response)

    async def _handle_get_full_image(self, connection: IPCConnection, data):
        """Handle get_full_image action"""
        item_id = data.get("id")
        if item_id:
            item = self.db_service.get_item(item_id)
            if item and (item["type"].startswith("image/") or item["type"] == "screenshot"):
                full_image_b64 = base64.b64encode(item["data"]).decode("utf-8")
                response = {"type": "full_image", "id": item_id, "content": full_image_b64}
                await connection.send_json(response)
            elif item and item["type"] == "file":
                separator = b'\n---FILE_CONTENT---\n'
                if separator in item["data"]:
                    _, file_content = item["data"].split(separator, 1)
                    file_content_b64 = base64.b64encode(file_content).decode("utf-8")
                    response = {"type": "full_file", "id": item_id, "content": file_content_b64}
                    await connection.send_json(response)
                else:
                    response = {"type": "error", "message": "Invalid file data format"}
                    await connection.send_json(response)

    async def _handle_delete_item(self, connection: IPCConnection, data):
        """Handle delete_item action"""
        item_id = data.get("id")
        if item_id:
            self.db_service.delete_item(item_id)
            await self.broadcast({"type": "item_deleted", "id": item_id})

    async def _handle_get_recently_pasted(self, connection: IPCConnection, data):
        """Handle get_recently_pasted action"""
        limit = data.get("limit", self.settings_service.max_page_length)
        offset = data.get("offset", 0)
        sort_order = data.get("sort_order", "DESC")
        filters = data.get("filters", [])

        items = self.db_service.get_recently_pasted(limit=limit, offset=offset, sort_order=sort_order, filters=filters)
        total_count = self.db_service.get_pasted_count()

        ui_items = [self.prepare_item_for_ui(item) for item in items]

        for i, item in enumerate(items):
            ui_items[i]["pasted_timestamp"] = item["pasted_timestamp"]

        logger.info(f"Sending {len(ui_items)} pasted items (total: {total_count}, offset: {offset})")
        response = {"type": "recently_pasted", "items": ui_items, "total_count": total_count, "offset": offset}
        await connection.send_json(response)

    async def _handle_record_paste(self, connection: IPCConnection, data):
        """Handle record_paste action"""
        item_id = data.get("id")
        if item_id:
            logger.info(f"Received record_paste request for item {item_id}")
            paste_id = self.db_service.add_pasted_item(item_id)
            logger.info(f"Recorded paste for item {item_id} (paste_id={paste_id})")
            response = {"type": "paste_recorded", "success": True, "paste_id": paste_id}
            await connection.send_json(response)

    async def _handle_search(self, connection: IPCConnection, data):
        """Handle search action"""
        query = data.get("query", "").strip()
        limit = data.get("limit", 100)
        filters = data.get("filters", [])

        if query:
            logger.info(f"Searching for: '{query}' (limit={limit}, filters={filters})")
            results = self.db_service.search_items(query, limit, filters)
            ui_items = [self.prepare_item_for_ui(item) for item in results]
            response = {"type": "search_results", "query": query, "items": ui_items, "count": len(ui_items)}
            await connection.send_json(response)
            logger.info(f"Search complete: {len(ui_items)} results")
        else:
            response = {"type": "search_results", "query": "", "items": [], "count": 0}
            await connection.send_json(response)

    async def _handle_get_tags(self, connection: IPCConnection):
        """Handle get_tags action"""
        logger.info("Fetching all tags")
        tags = self.db_service.get_all_tags()
        response = {"type": "tags", "tags": tags}
        await connection.send_json(response)
        logger.info(f"Sent {len(tags)} tags")

    async def _handle_create_tag(self, connection: IPCConnection, data):
        """Handle create_tag action"""
        name = data.get("name")
        description = data.get("description")
        color = data.get("color")

        if name:
            logger.info(f"Creating tag: '{name}'")
            try:
                tag_id = self.db_service.create_tag(name, description, color)
                tag = self.db_service.get_tag(tag_id)
                response = {"type": "tag_created", "tag": tag, "success": True}
                await connection.send_json(response)
                logger.info(f"Created tag: ID={tag_id}, Name='{name}'")
            except Exception as e:
                response = {"type": "tag_created", "success": False, "error": str(e)}
                await connection.send_json(response)
                logger.error(f"Failed to create tag: {e}")
        else:
            response = {"type": "tag_created", "success": False, "error": "Name is required"}
            await connection.send_json(response)

    async def _handle_update_tag(self, connection: IPCConnection, data):
        """Handle update_tag action"""
        tag_id = data.get("tag_id")
        name = data.get("name")
        description = data.get("description")
        color = data.get("color")

        if tag_id:
            logger.info(f"Updating tag ID={tag_id}")
            success = self.db_service.update_tag(tag_id, name, description, color)
            if success:
                tag = self.db_service.get_tag(tag_id)
            response = {"type": "tag_updated", "tag": tag if success else None, "success": success}
            await connection.send_json(response)
            logger.info(f"Updated tag ID={tag_id}: {success}")
        else:
            response = {"type": "tag_updated", "success": False, "error": "tag_id is required"}
            await connection.send_json(response)

    async def _handle_delete_tag(self, connection: IPCConnection, data):
        """Handle delete_tag action"""
        tag_id = data.get("tag_id")

        if tag_id:
            logger.info(f"Deleting tag ID={tag_id}")
            success = self.db_service.delete_tag(tag_id)
            response = {"type": "tag_deleted", "tag_id": tag_id, "success": success}
            await connection.send_json(response)
            logger.info(f"Deleted tag ID={tag_id}: {success}")
        else:
            response = {"type": "tag_deleted", "success": False, "error": "tag_id is required"}
            await connection.send_json(response)

    async def _handle_add_tag(self, connection: IPCConnection, data):
        """Handle add_tag action"""
        item_id = data.get("item_id")
        tag_id = data.get("tag_id")

        if item_id and tag_id:
            logger.info(f"Adding tag {tag_id} to item {item_id}")
            success = self.db_service.add_tag_to_item(item_id, tag_id)

            if success:
                response = {"type": "tag_added", "item_id": item_id, "tag_id": tag_id, "success": True}
                logger.info(f"Tag {tag_id} added to item {item_id}")
            else:
                response = {"type": "tag_added", "success": False, "error": "Failed to add tag"}
                logger.error(f"Failed to add tag {tag_id} to item {item_id}")

            await connection.send_json(response)
        else:
            response = {"type": "tag_added", "success": False, "error": "item_id and tag_id are required"}
            await connection.send_json(response)

    async def _handle_remove_tag(self, connection: IPCConnection, data):
        """Handle remove_tag action"""
        item_id = data.get("item_id")
        tag_id = data.get("tag_id")

        if item_id and tag_id:
            logger.info(f"Removing tag {tag_id} from item {item_id}")
            success = self.db_service.remove_tag_from_item(item_id, tag_id)

            if success:
                response = {"type": "tag_removed", "item_id": item_id, "tag_id": tag_id, "success": True}
                logger.info(f"Tag {tag_id} removed from item {item_id}")
            else:
                response = {"type": "tag_removed", "success": False, "error": "Failed to remove tag"}
                logger.error(f"Failed to remove tag {tag_id} from item {item_id}")

            await connection.send_json(response)
        else:
            response = {"type": "tag_removed", "success": False, "error": "item_id and tag_id are required"}
            await connection.send_json(response)

    async def _handle_get_item_tags(self, connection: IPCConnection, data):
        """Handle get_item_tags action"""
        item_id = data.get("item_id")

        if item_id:
            logger.info(f"Fetching tags for item {item_id}")
            tags = self.db_service.get_tags_for_item(item_id)
            response = {"type": "item_tags", "item_id": item_id, "tags": tags}
            await connection.send_json(response)
            logger.info(f"Sent {len(tags)} tags for item {item_id}")
        else:
            response = {"type": "item_tags", "tags": [], "error": "item_id is required"}
            await connection.send_json(response)

    async def _handle_get_items_by_tags(self, connection: IPCConnection, data):
        """Handle get_items_by_tags action"""
        tag_ids = data.get("tag_ids", [])
        match_all = data.get("match_all", False)
        limit = data.get("limit", 100)
        offset = data.get("offset", 0)

        if tag_ids:
            logger.info(f"Fetching items by tags: {tag_ids} (match_all={match_all})")
            results = self.db_service.get_items_by_tags(tag_ids, match_all, limit, offset)
            ui_items = [self.prepare_item_for_ui(item) for item in results]
            response = {"type": "items_by_tags", "items": ui_items, "count": len(ui_items)}
            await connection.send_json(response)
            logger.info(f"Sent {len(ui_items)} items for tags {tag_ids}")
        else:
            response = {"type": "items_by_tags", "items": [], "count": 0}
            await connection.send_json(response)

    async def _handle_update_item_name(self, connection: IPCConnection, data):
        """Handle update_item_name action"""
        item_id = data.get("item_id")
        name = data.get("name")

        if item_id is not None:
            logger.info(f"Updating name for item {item_id}: '{name}'")
            success = self.db_service.update_item_name(item_id, name)
            response = {"type": "item_name_updated", "item_id": item_id, "name": name, "success": success}
            await connection.send_json(response)

            if success:
                await self.broadcast({"type": "item_updated", "item_id": item_id, "name": name})
            logger.info(f"Updated name for item {item_id}: {success}")
        else:
            response = {"type": "item_name_updated", "success": False, "error": "item_id is required"}
            await connection.send_json(response)

    async def _handle_toggle_secret(self, connection: IPCConnection, data):
        """Handle toggle_secret action"""
        item_id = data.get("item_id")
        is_secret = data.get("is_secret", False)
        name = data.get("name")

        if item_id is not None:
            logger.info(f"Toggling secret for item {item_id}: is_secret={is_secret}, name='{name}'")
            success = self.db_service.toggle_secret(item_id, is_secret, name)

            if success:
                updated_item = self.db_service.get_item(item_id)
                response = {
                    "type": "secret_toggled",
                    "item_id": item_id,
                    "is_secret": is_secret,
                    "name": updated_item.get("name") if updated_item else name,
                    "success": True
                }
                await connection.send_json(response)
                logger.info(f"Sent secret_toggled response for item {item_id}")

                await self.broadcast({
                    "type": "item_updated",
                    "item_id": item_id,
                    "is_secret": is_secret,
                    "name": updated_item.get("name") if updated_item else name
                })
            else:
                response = {
                    "type": "secret_toggled",
                    "success": False,
                    "error": "Secret items must have a name"
                }
                await connection.send_json(response)
            logger.info(f"Toggled secret for item {item_id}: {success}")
        else:
            response = {"type": "secret_toggled", "success": False, "error": "item_id is required"}
            await connection.send_json(response)

    async def _handle_toggle_favorite(self, connection: IPCConnection, data):
        """Handle toggle_favorite action"""
        item_id = data.get("item_id")
        is_favorite = data.get("is_favorite", False)

        if item_id is not None:
            logger.info(f"Toggling favorite for item {item_id}: is_favorite={is_favorite}")
            success = self.db_service.toggle_favorite(item_id, is_favorite)

            if success:
                response = {
                    "type": "favorite_toggled",
                    "item_id": item_id,
                    "is_favorite": is_favorite,
                    "success": True
                }
                await connection.send_json(response)
                logger.info(f"Sent favorite_toggled response for item {item_id}")

                await self.broadcast({
                    "type": "item_updated",
                    "item_id": item_id,
                    "is_favorite": is_favorite
                })
            else:
                response = {
                    "type": "favorite_toggled",
                    "success": False,
                    "error": "Failed to toggle favorite status"
                }
                await connection.send_json(response)
            logger.info(f"Toggled favorite for item {item_id}: {success}")
        else:
            response = {"type": "favorite_toggled", "success": False, "error": "item_id is required"}
            await connection.send_json(response)

    async def _handle_get_item(self, connection: IPCConnection, data):
        """Handle get_item action"""
        item_id = data.get("item_id")
        if item_id is not None:
            logger.info(f"Fetching item {item_id}")
            item = self.db_service.get_item(item_id)

            if item:
                ui_item = self.prepare_item_for_ui(item)
                response = {"type": "item", "item": ui_item}
                logger.info(f"Sending item {item_id} to client")
            else:
                response = {"type": "item", "item": None, "error": "Item not found"}
                logger.warning(f"Item {item_id} not found")

            await connection.send_json(response)
        else:
            response = {"type": "item", "item": None, "error": "item_id is required"}
            await connection.send_json(response)

    async def _handle_get_file_extensions(self, connection: IPCConnection):
        """Handle get_file_extensions action"""
        logger.info("Fetching file extensions")
        extensions = self.db_service.get_file_extensions()
        response = {"type": "file_extensions", "extensions": extensions}
        await connection.send_json(response)
        logger.info(f"Sent {len(extensions)} file extensions")

    async def _handle_clipboard_event(self, data):
        """Handle clipboard_event action"""
        event_data = data.get("data", {})
        logger.info(f"Received clipboard event via IPC: {event_data.get('type', 'unknown')}")
        self.clipboard_service.handle_clipboard_event(event_data)

    async def _handle_shutdown(self, connection: IPCConnection):
        """Handle shutdown action - gracefully shutdown the server"""
        logger.info("Received shutdown request via IPC")
        response = {"type": "shutdown_acknowledged"}
        await connection.send_json(response)
        logger.info("Shutdown acknowledged, initiating graceful shutdown...")

        # Close database connection
        try:
            logger.info("Closing database connection...")
            self.db_service.close()
            logger.info("Database connection closed")
        except Exception as e:
            logger.error(f"Error closing database: {e}")

        # Schedule immediate process exit from event loop
        # os._exit() bypasses Python cleanup and exits immediately
        import os
        import asyncio

        def force_exit():
            logger.info("Forcing process exit...")
            os._exit(0)

        # Schedule exit after brief delay to allow response to send
        asyncio.get_event_loop().call_later(0.1, force_exit)

    async def _handle_get_total_count(self, connection: IPCConnection):
        """Handle get_total_count action"""
        total = self.db_service.get_total_count()
        response = {"type": "total_count", "total": total}
        await connection.send_json(response)
        logger.info(f"Sent total count: {total}")

    async def _handle_update_retention_settings(self, connection: IPCConnection, data):
        """Handle update_retention_settings action"""
        enabled = data.get("enabled", True)
        max_items = data.get("max_items", 250)
        delete_count = data.get("delete_count", 0)

        logger.info(f"Updating retention settings: enabled={enabled}, max_items={max_items}, delete_count={delete_count}")

        try:
            # Delete items if requested
            deleted = 0
            if delete_count > 0:
                deleted = self.db_service.bulk_delete_oldest(delete_count)
                logger.info(f"Deleted {deleted} oldest items")

            # Update settings
            self.settings_service.update_settings(
                **{
                    "retention.enabled": enabled,
                    "retention.max_items": max_items
                }
            )

            response = {
                "status": "success",
                "deleted": deleted,
                "message": f"Retention settings updated. {deleted} items deleted."
            }
            await connection.send_json(response)

            # Broadcast update to all clients to refresh their views
            await self.broadcast({
                "type": "retention_updated",
                "enabled": enabled,
                "max_items": max_items,
                "deleted": deleted
            })

        except Exception as e:
            logger.error(f"Error updating retention settings: {e}")
            response = {
                "status": "error",
                "message": str(e)
            }
            await connection.send_json(response)

    async def _handle_update_clipboard_settings(self, connection: IPCConnection, data):
        """Handle update_clipboard_settings action"""
        refocus_on_copy = data.get("refocus_on_copy")

        logger.info(f"Updating clipboard settings: refocus_on_copy={refocus_on_copy}")

        try:
            # Update settings
            if refocus_on_copy is not None:
                self.settings_service.update_settings(
                    **{"clipboard.refocus_on_copy": refocus_on_copy}
                )

            response = {
                "status": "success",
                "message": "Clipboard settings updated.",
                "refocus_on_copy": refocus_on_copy
            }
            await connection.send_json(response)

            # Broadcast update to all clients
            await self.broadcast({
                "type": "clipboard_settings_updated",
                "refocus_on_copy": refocus_on_copy
            })

        except Exception as e:
            logger.error(f"Error updating clipboard settings: {e}")
            response = {
                "status": "error",
                "message": str(e)
            }
            await connection.send_json(response)

    async def broadcast(self, message: dict):
        """Broadcast message to all IPC clients"""
        if self.clients:
            # Create tasks for all sends but don't wait for all to complete
            tasks = []
            for client in list(self.clients):  # Create a copy to avoid modification during iteration
                if not client.closed:
                    tasks.append(client.send_json(message))

            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
