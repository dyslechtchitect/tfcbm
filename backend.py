#!/usr/bin/env python3
"""
TFCBM Backend - WebSocket server for UI
Serves clipboard items from SQLite database
"""

import asyncio
import websockets
import json
import base64
import threading
import time
from datetime import datetime
from database import ClipboardDB


class ClipboardBackend:
    """WebSocket backend for clipboard UI"""

    def __init__(self, host='localhost', port=8765):
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
        item_type = item['type']
        data = item['data']

        if item_type == 'text':
            # Text data stored as bytes, convert to string
            content = data.decode('utf-8') if isinstance(data, bytes) else data
        elif item_type.startswith('image/') or item_type == 'screenshot':
            # Image data already in bytes, convert to base64
            content = base64.b64encode(data).decode('utf-8') if isinstance(data, bytes) else data
        else:
            # Unknown type, try to decode as text
            try:
                content = data.decode('utf-8') if isinstance(data, bytes) else data
            except:
                content = base64.b64encode(data).decode('utf-8') if isinstance(data, bytes) else data

        return {
            'id': item['id'],
            'type': item_type,
            'content': content,
            'timestamp': item['timestamp']
        }

    async def handle_client(self, websocket, path):
        """Handle WebSocket client connection"""
        print(f"Client connected from {websocket.remote_address}")
        self.clients.add(websocket)

        try:
            async for message in websocket:
                data = json.loads(message)
                action = data.get('action')

                if action == 'get_history':
                    # Send all items
                    limit = data.get('limit', 100)
                    items = self.db.get_items(limit=limit)

                    # Convert to UI format
                    ui_items = [self.prepare_item_for_ui(item) for item in items]

                    response = {
                        'type': 'history',
                        'items': ui_items
                    }
                    await websocket.send(json.dumps(response))

                elif action == 'delete_item':
                    item_id = data.get('id')
                    if item_id:
                        self.db.delete_item(item_id)
                        # Notify all clients
                        await self.broadcast({
                            'type': 'item_deleted',
                            'id': item_id
                        })

        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.clients.remove(websocket)
            print(f"Client disconnected")

    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        if self.clients:
            message_json = json.dumps(message)
            await asyncio.gather(
                *[client.send(message_json) for client in self.clients],
                return_exceptions=True
            )

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
                            message = {
                                'type': 'new_item',
                                'item': ui_item
                            }

                            # Schedule broadcast in async loop
                            asyncio.run_coroutine_threadsafe(
                                self.broadcast(message),
                                self.loop
                            )

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


if __name__ == '__main__':
    asyncio.run(main())
