#!/usr/bin/env python3
"""
TFCBM Backend - WebSocket server for UI
Serves clipboard items from SQLite database
"""

import asyncio
import base64
import json
import threading
import time

import websockets

from database import ClipboardDB


class ClipboardBackend:
    """WebSocket backend for clipboard UI"""

    def __init__(self, host="localhost", port=8765):
        self.host = host
        self.port = port
        self.db = ClipboardDB()
        self.clients = set()
        self.last_known_id = self.db.get_latest_id() or 0
        self.running = True

    def prepare_item_for_ui(self, item: dict) -> dict:
        """
        Convert database item to UI-renderable format

        Args:
            item: Dict with 'id', 'timestamp', 'type', 'data' (bytes)

        Returns:
            Dict ready to send to UI
        """
        item_type = item["type"]
        data = item["data"]

        if item_type == "text":
            # Text data stored as bytes, convert to string
            content = data.decode("utf-8") if isinstance(data, bytes) else data
        elif item_type.startswith("image/") or item_type == "screenshot":
            # Image data already in bytes, convert to base64
            content = base64.b64encode(data).decode("utf-8") if isinstance(data, bytes) else data
        else:
            # Unknown type, try to decode as text
            try:
                content = data.decode("utf-8") if isinstance(data, bytes) else data
            except BaseException:
                content = base64.b64encode(data).decode("utf-8") if isinstance(data, bytes) else data

        # Build UI item with all fields
        ui_item = {
            "id": item["id"],
            "type": item_type,
            "content": content,
            "timestamp": item["timestamp"],
            "name": item.get("name"),
            "is_secret": item.get("is_secret", False),
            # Support both pasted_at and pasted_timestamp field names
            "pasted_at": item.get("pasted_at") or item.get("pasted_timestamp"),
        }

        # Add tags - check if already included in item, otherwise fetch
        if "tags" in item:
            ui_item["tags"] = item["tags"]
        else:
            item_id = item["id"]
            tags = self.db.get_tags_for_item(item_id)
            ui_item["tags"] = tags

        return ui_item

    async def handle_client(self, websocket):
        """Handle WebSocket client connection"""
        print(f"Client connected from {websocket.remote_address}")
        self.clients.add(websocket)

        try:
            async for message in websocket:
                data = json.loads(message)
                action = data.get("action")

                if action == "get_history":
                    # Send all items
                    limit = data.get("limit", 100)
                    offset = data.get("offset", 0)
                    sort_order = data.get("sort_order", "DESC")
                    filters = data.get("filters", None)

                    print(f"[BACKEND] get_history: limit={limit}, offset={offset}, sort_order={sort_order}, filters={filters}")

                    items = self.db.get_items(
                        limit=limit,
                        offset=offset,
                        sort_order=sort_order,
                        filters=filters
                    )

                    # Convert to UI format
                    ui_items = [self.prepare_item_for_ui(item) for item in items]

                    # Get total count for pagination
                    total_count = self.db.get_total_count()

                    response = {"type": "history", "items": ui_items, "total_count": total_count, "offset": offset}
                    await websocket.send(json.dumps(response))

                elif action == "get_recently_pasted":
                    # Get recently pasted items
                    limit = data.get("limit", 100)
                    offset = data.get("offset", 0)
                    sort_order = data.get("sort_order", "DESC")
                    filters = data.get("filters", None)

                    print(f"[BACKEND] get_recently_pasted: limit={limit}, offset={offset}, sort_order={sort_order}, filters={filters}")

                    items = self.db.get_recently_pasted(
                        limit=limit,
                        offset=offset,
                        sort_order=sort_order,
                        filters=filters
                    )

                    # Convert to UI format
                    ui_items = [self.prepare_item_for_ui(item) for item in items]

                    # Get total count for pagination
                    total_count = self.db.get_pasted_count()

                    response = {"type": "recently_pasted", "items": ui_items, "total_count": total_count, "offset": offset}
                    await websocket.send(json.dumps(response))

                elif action == "get_tags":
                    # Get all tags
                    print("[BACKEND] get_tags request")
                    tags = self.db.get_all_tags()
                    response = {"type": "tags", "tags": tags}
                    await websocket.send(json.dumps(response))

                elif action == "create_tag":
                    # Create new tag
                    name = data.get("name")
                    color = data.get("color", "#808080")
                    print(f"[BACKEND] create_tag: name={name}, color={color}")
                    tag_id = self.db.create_tag(name, color)
                    response = {"type": "tag_created", "tag_id": tag_id, "name": name, "color": color}
                    await websocket.send(json.dumps(response))

                elif action == "update_tag":
                    # Update existing tag
                    tag_id = data.get("tag_id")
                    name = data.get("name")
                    color = data.get("color")
                    print(f"[BACKEND] update_tag: id={tag_id}, name={name}, color={color}")
                    self.db.update_tag(tag_id, name, color)
                    response = {"type": "tag_updated", "tag_id": tag_id}
                    await websocket.send(json.dumps(response))

                elif action == "delete_tag":
                    # Delete tag
                    tag_id = data.get("tag_id")
                    print(f"[BACKEND] delete_tag: id={tag_id}")
                    self.db.delete_tag(tag_id)
                    response = {"type": "tag_deleted", "tag_id": tag_id}
                    await websocket.send(json.dumps(response))

                elif action == "add_item_tag":
                    # Add tag to item
                    item_id = data.get("item_id")
                    tag_id = data.get("tag_id")
                    print(f"[BACKEND] add_item_tag: item_id={item_id}, tag_id={tag_id}")
                    success = self.db.add_tag_to_item(item_id, tag_id)
                    response = {"type": "item_tag_added", "item_id": item_id, "tag_id": tag_id, "success": success}
                    await websocket.send(json.dumps(response))

                elif action == "remove_item_tag":
                    # Remove tag from item
                    item_id = data.get("item_id")
                    tag_id = data.get("tag_id")
                    print(f"[BACKEND] remove_item_tag: item_id={item_id}, tag_id={tag_id}")
                    success = self.db.remove_tag_from_item(item_id, tag_id)
                    response = {"type": "item_tag_removed", "item_id": item_id, "tag_id": tag_id, "success": success}
                    await websocket.send(json.dumps(response))

                elif action == "get_item_tags":
                    # Get tags for a specific item
                    item_id = data.get("item_id")
                    print(f"[BACKEND] get_item_tags: item_id={item_id}")
                    tags = self.db.get_tags_for_item(item_id)
                    response = {"type": "item_tags", "item_id": item_id, "tags": tags}
                    await websocket.send(json.dumps(response))

                elif action == "toggle_secret":
                    # Toggle secret status of an item
                    item_id = data.get("item_id")
                    is_secret = data.get("is_secret")
                    name = data.get("name")

                    print(f"[BACKEND] toggle_secret: item_id={item_id}, is_secret={is_secret}, name={name}")

                    success = self.db.toggle_secret(item_id, is_secret, name)

                    if success:
                        # Get updated item to return current state
                        item = self.db.get_item(item_id)
                        response = {
                            "type": "secret_toggled",
                            "success": True,
                            "item_id": item_id,
                            "is_secret": item.get("is_secret", False) if item else is_secret,
                            "name": item.get("name") if item else name
                        }
                    else:
                        response = {
                            "type": "secret_toggled",
                            "success": False,
                            "item_id": item_id,
                            "error": "Failed to toggle secret status"
                        }

                    await websocket.send(json.dumps(response))

                elif action == "search":
                    # Search for items
                    query = data.get("query", "")
                    limit = data.get("limit", 100)
                    filters = data.get("filters", None)

                    print(f"[BACKEND] search: query='{query}', limit={limit}, filters={filters}")

                    items = self.db.search_items(query, limit=limit, filters=filters)

                    # Convert to UI format
                    ui_items = [self.prepare_item_for_ui(item) for item in items]

                    response = {"type": "search_results", "items": ui_items, "count": len(ui_items)}
                    await websocket.send(json.dumps(response))

                elif action == "delete_item":
                    item_id = data.get("id")
                    if item_id:
                        self.db.delete_item(item_id)
                        # Notify all clients
                        await self.broadcast({"type": "item_deleted", "id": item_id})

        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.clients.remove(websocket)
            print(f"Client disconnected")

    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        if self.clients:
            message_json = json.dumps(message)
            await asyncio.gather(*[client.send(message_json) for client in self.clients], return_exceptions=True)

    def watch_for_new_items(self):
        """Background thread to watch for new database items"""
        print("Starting database watcher...")

        while self.running:
            try:
                latest_id = self.db.get_latest_id()

                if latest_id and latest_id > self.last_known_id:
                    # New items detected
                    for item_id in range(self.last_known_id + 1, latest_id + 1):
                        item = self.db.get_item(item_id)
                        if item:
                            ui_item = self.prepare_item_for_ui(item)

                            # Broadcast to all clients
                            message = {"type": "new_item", "item": ui_item}

                            # Schedule broadcast in async loop
                            asyncio.run_coroutine_threadsafe(self.broadcast(message), self.loop)

                    self.last_known_id = latest_id

            except Exception as e:
                print(f"Error in watcher: {e}")

            time.sleep(0.5)  # Check every 500ms

    async def start(self):
        """Start WebSocket server"""
        # Start database watcher in background thread
        self.loop = asyncio.get_event_loop()
        watcher_thread = threading.Thread(target=self.watch_for_new_items, daemon=True)
        watcher_thread.start()

        # Start WebSocket server
        print(f"WebSocket server starting on ws://{self.host}:{self.port}")
        async with websockets.serve(self.handle_client, self.host, self.port):
            print("WebSocket server ready")
            await asyncio.Future()  # Run forever

    def stop(self):
        """Stop the backend"""
        self.running = False
        self.db.close()


async def main():
    backend = ClipboardBackend()
    try:
        await backend.start()
    except KeyboardInterrupt:
        print("\nStopping backend...")
        backend.stop()


if __name__ == "__main__":
    asyncio.run(main())
