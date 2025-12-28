#!/usr/bin/env python3
"""
WebSocket Service - Handles WebSocket communication with UI
"""
import asyncio
import base64
import json
import logging
from typing import Set, Optional

import websockets

logger = logging.getLogger(__name__)


class WebSocketService:
    """Service for WebSocket communication with UI clients"""

    def __init__(self, database_service, settings_service, clipboard_service):
        """
        Initialize WebSocket service

        Args:
            database_service: Database service
            settings_service: Settings service
            clipboard_service: Clipboard service
        """
        logger.info("[WebSocketService.__init__] Starting initialization...")
        self.db_service = database_service
        self.settings_service = settings_service
        self.clipboard_service = clipboard_service
        self.clients: Set = set()
        self.ui_pid: Optional[int] = None
        self.last_known_id = database_service.get_latest_id() or 0
        logger.info("[WebSocketService.__init__] Initialization complete")

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
                from server.src.services.thumbnail_service import ThumbnailService
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
        }

    async def websocket_handler(self, websocket):
        """Handle WebSocket client connections from UI"""
        logger.info(f"WebSocket client connected from {websocket.remote_address}")
        self.clients.add(websocket)

        try:
            async for message in websocket:
                try:
                    await self._handle_message(websocket, message)
                except Exception as e:
                    logger.error(f"Error handling WebSocket message: {e}")
                    import traceback
                    traceback.print_exc()

        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            logger.error(f"WebSocket handler error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.clients.remove(websocket)
            logger.info("WebSocket client disconnected")

    async def _handle_message(self, websocket, message: str):
        """Handle individual WebSocket message"""
        data = json.loads(message)
        action = data.get("action")

        if action == "get_history":
            await self._handle_get_history(websocket, data)
        elif action == "register_ui_pid":
            await self._handle_register_ui_pid(websocket, data)
        elif action == "get_full_image":
            await self._handle_get_full_image(websocket, data)
        elif action == "delete_item":
            await self._handle_delete_item(websocket, data)
        elif action == "get_recently_pasted":
            await self._handle_get_recently_pasted(websocket, data)
        elif action == "record_paste":
            await self._handle_record_paste(websocket, data)
        elif action == "search":
            await self._handle_search(websocket, data)
        elif action == "get_tags":
            await self._handle_get_tags(websocket)
        elif action == "create_tag":
            await self._handle_create_tag(websocket, data)
        elif action == "update_tag":
            await self._handle_update_tag(websocket, data)
        elif action == "delete_tag":
            await self._handle_delete_tag(websocket, data)
        elif action == "add_item_tag" or action == "add_tag":
            await self._handle_add_tag(websocket, data)
        elif action == "remove_item_tag" or action == "remove_tag":
            await self._handle_remove_tag(websocket, data)
        elif action == "get_item_tags":
            await self._handle_get_item_tags(websocket, data)
        elif action == "get_items_by_tags":
            await self._handle_get_items_by_tags(websocket, data)
        elif action == "update_item_name":
            await self._handle_update_item_name(websocket, data)
        elif action == "toggle_secret":
            await self._handle_toggle_secret(websocket, data)
        elif action == "get_item":
            await self._handle_get_item(websocket, data)
        elif action == "get_file_extensions":
            await self._handle_get_file_extensions(websocket)
        elif action == "get_total_count":
            await self._handle_get_total_count(websocket)
        elif action == "update_retention_settings":
            await self._handle_update_retention_settings(websocket, data)
        elif action == "clipboard_event":
            await self._handle_clipboard_event(data)
        else:
            logger.warning(f"Unknown WebSocket action: {action}")

    async def _handle_get_history(self, websocket, data):
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
        await websocket.send(json.dumps(response))

    async def _handle_register_ui_pid(self, websocket, data):
        """Handle register_ui_pid action"""
        pid = data.get("pid")
        if pid:
            self.ui_pid = pid
            logger.info(f"Registered UI PID: {self.ui_pid}")
            response = {"type": "ui_pid_registered", "success": True}
        else:
            response = {"type": "ui_pid_registered", "success": False, "error": "pid is required"}
        await websocket.send(json.dumps(response))

    async def _handle_get_full_image(self, websocket, data):
        """Handle get_full_image action"""
        item_id = data.get("id")
        if item_id:
            item = self.db_service.get_item(item_id)
            if item and (item["type"].startswith("image/") or item["type"] == "screenshot"):
                full_image_b64 = base64.b64encode(item["data"]).decode("utf-8")
                response = {"type": "full_image", "id": item_id, "content": full_image_b64}
                await websocket.send(json.dumps(response))
            elif item and item["type"] == "file":
                separator = b'\n---FILE_CONTENT---\n'
                if separator in item["data"]:
                    _, file_content = item["data"].split(separator, 1)
                    file_content_b64 = base64.b64encode(file_content).decode("utf-8")
                    response = {"type": "full_file", "id": item_id, "content": file_content_b64}
                    await websocket.send(json.dumps(response))
                else:
                    response = {"type": "error", "message": "Invalid file data format"}
                    await websocket.send(json.dumps(response))

    async def _handle_delete_item(self, websocket, data):
        """Handle delete_item action"""
        item_id = data.get("id")
        if item_id:
            self.db_service.delete_item(item_id)
            await self.broadcast({"type": "item_deleted", "id": item_id})

    async def _handle_get_recently_pasted(self, websocket, data):
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
        await websocket.send(json.dumps(response))

    async def _handle_record_paste(self, websocket, data):
        """Handle record_paste action"""
        item_id = data.get("id")
        if item_id:
            logger.info(f"Received record_paste request for item {item_id}")
            paste_id = self.db_service.add_pasted_item(item_id)
            logger.info(f"Recorded paste for item {item_id} (paste_id={paste_id})")
            response = {"type": "paste_recorded", "success": True, "paste_id": paste_id}
            await websocket.send(json.dumps(response))

    async def _handle_search(self, websocket, data):
        """Handle search action"""
        query = data.get("query", "").strip()
        limit = data.get("limit", 100)
        filters = data.get("filters", [])

        if query:
            logger.info(f"Searching for: '{query}' (limit={limit}, filters={filters})")
            results = self.db_service.search_items(query, limit, filters)
            ui_items = [self.prepare_item_for_ui(item) for item in results]
            response = {"type": "search_results", "query": query, "items": ui_items, "count": len(ui_items)}
            await websocket.send(json.dumps(response))
            logger.info(f"Search complete: {len(ui_items)} results")
        else:
            response = {"type": "search_results", "query": "", "items": [], "count": 0}
            await websocket.send(json.dumps(response))

    async def _handle_get_tags(self, websocket):
        """Handle get_tags action"""
        logger.info("Fetching all tags")
        tags = self.db_service.get_all_tags()
        response = {"type": "tags", "tags": tags}
        await websocket.send(json.dumps(response))
        logger.info(f"Sent {len(tags)} tags")

    async def _handle_create_tag(self, websocket, data):
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
                await websocket.send(json.dumps(response))
                logger.info(f"Created tag: ID={tag_id}, Name='{name}'")
            except Exception as e:
                response = {"type": "tag_created", "success": False, "error": str(e)}
                await websocket.send(json.dumps(response))
                logger.error(f"Failed to create tag: {e}")
        else:
            response = {"type": "tag_created", "success": False, "error": "Name is required"}
            await websocket.send(json.dumps(response))

    async def _handle_update_tag(self, websocket, data):
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
            await websocket.send(json.dumps(response))
            logger.info(f"Updated tag ID={tag_id}: {success}")
        else:
            response = {"type": "tag_updated", "success": False, "error": "tag_id is required"}
            await websocket.send(json.dumps(response))

    async def _handle_delete_tag(self, websocket, data):
        """Handle delete_tag action"""
        tag_id = data.get("tag_id")

        if tag_id:
            logger.info(f"Deleting tag ID={tag_id}")
            success = self.db_service.delete_tag(tag_id)
            response = {"type": "tag_deleted", "tag_id": tag_id, "success": success}
            await websocket.send(json.dumps(response))
            logger.info(f"Deleted tag ID={tag_id}: {success}")
        else:
            response = {"type": "tag_deleted", "success": False, "error": "tag_id is required"}
            await websocket.send(json.dumps(response))

    async def _handle_add_tag(self, websocket, data):
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

            await websocket.send(json.dumps(response))
        else:
            response = {"type": "tag_added", "success": False, "error": "item_id and tag_id are required"}
            await websocket.send(json.dumps(response))

    async def _handle_remove_tag(self, websocket, data):
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

            await websocket.send(json.dumps(response))
        else:
            response = {"type": "tag_removed", "success": False, "error": "item_id and tag_id are required"}
            await websocket.send(json.dumps(response))

    async def _handle_get_item_tags(self, websocket, data):
        """Handle get_item_tags action"""
        item_id = data.get("item_id")

        if item_id:
            logger.info(f"Fetching tags for item {item_id}")
            tags = self.db_service.get_tags_for_item(item_id)
            response = {"type": "item_tags", "item_id": item_id, "tags": tags}
            await websocket.send(json.dumps(response))
            logger.info(f"Sent {len(tags)} tags for item {item_id}")
        else:
            response = {"type": "item_tags", "tags": [], "error": "item_id is required"}
            await websocket.send(json.dumps(response))

    async def _handle_get_items_by_tags(self, websocket, data):
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
            await websocket.send(json.dumps(response))
            logger.info(f"Sent {len(ui_items)} items for tags {tag_ids}")
        else:
            response = {"type": "items_by_tags", "items": [], "count": 0}
            await websocket.send(json.dumps(response))

    async def _handle_update_item_name(self, websocket, data):
        """Handle update_item_name action"""
        item_id = data.get("item_id")
        name = data.get("name")

        if item_id is not None:
            logger.info(f"Updating name for item {item_id}: '{name}'")
            success = self.db_service.update_item_name(item_id, name)
            response = {"type": "item_name_updated", "item_id": item_id, "name": name, "success": success}
            await websocket.send(json.dumps(response))

            if success:
                await self.broadcast({"type": "item_updated", "item_id": item_id, "name": name})
            logger.info(f"Updated name for item {item_id}: {success}")
        else:
            response = {"type": "item_name_updated", "success": False, "error": "item_id is required"}
            await websocket.send(json.dumps(response))

    async def _handle_toggle_secret(self, websocket, data):
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
                await websocket.send(json.dumps(response))
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
                await websocket.send(json.dumps(response))
            logger.info(f"Toggled secret for item {item_id}: {success}")
        else:
            response = {"type": "secret_toggled", "success": False, "error": "item_id is required"}
            await websocket.send(json.dumps(response))

    async def _handle_get_item(self, websocket, data):
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

            await websocket.send(json.dumps(response))
        else:
            response = {"type": "item", "item": None, "error": "item_id is required"}
            await websocket.send(json.dumps(response))

    async def _handle_get_file_extensions(self, websocket):
        """Handle get_file_extensions action"""
        logger.info("Fetching file extensions")
        extensions = self.db_service.get_file_extensions()
        response = {"type": "file_extensions", "extensions": extensions}
        await websocket.send(json.dumps(response))
        logger.info(f"Sent {len(extensions)} file extensions")

    async def _handle_clipboard_event(self, data):
        """Handle clipboard_event action"""
        event_data = data.get("data", {})
        logger.info(f"Received clipboard event via WebSocket: {event_data.get('type', 'unknown')}")
        self.clipboard_service.handle_clipboard_event(event_data)

    async def _handle_get_total_count(self, websocket):
        """Handle get_total_count action"""
        total = self.db_service.get_total_count()
        response = {"type": "total_count", "total": total}
        await websocket.send(json.dumps(response))
        logger.info(f"Sent total count: {total}")

    async def _handle_update_retention_settings(self, websocket, data):
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
            await websocket.send(json.dumps(response))

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
            await websocket.send(json.dumps(response))

    async def broadcast(self, message: dict):
        """Broadcast message to all WebSocket clients"""
        if self.clients:
            message_json = json.dumps(message)
            await asyncio.gather(*[client.send(message_json) for client in self.clients], return_exceptions=True)
