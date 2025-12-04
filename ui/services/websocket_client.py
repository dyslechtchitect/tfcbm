"""WebSocket client for TFCBM backend communication."""

import asyncio
import json
import logging
import threading
from typing import Callable, Optional, Set

import websockets
from gi.repository import GLib

logger = logging.getLogger("TFCBM.WebSocketClient")


class WebSocketClient:
    def __init__(
        self,
        uri: str,
        max_size: int,
        on_message: Callable,
        on_error: Optional[Callable] = None,
    ):
        self.uri = uri
        self.max_size = max_size
        self.on_message = on_message
        self.on_error = on_error
        self._websocket = None
        self._thread = None
        self._loop = None
        self._is_connected = False
        self._reconnect_attempt = 0
        self._listener_running = False

    async def connect(self):
        self._is_connected = False
        self._reconnect_attempt = 0
        while not self._is_connected and self._reconnect_attempt < 5: # Retry 5 times
            try:
                logger.info(f"Connecting to WebSocket server at {self.uri} (attempt {self._reconnect_attempt + 1})...")
                self._websocket = await websockets.connect(self.uri, max_size=self.max_size, open_timeout=5) # 5 seconds timeout
                self._is_connected = True
                logger.info("Connected to WebSocket server")
                await self._listen_for_messages()
            except websockets.exceptions.ConnectionClosedError:
                logger.info("WebSocket connection closed")
                self._is_connected = False
                break # Exit retry loop if connection was closed cleanly
            except Exception as e:
                self._is_connected = False
                self._reconnect_attempt += 1
                logger.warning(f"WebSocket connection failed: {e}. Retrying in {2 ** self._reconnect_attempt} seconds...")
                await asyncio.sleep(2 ** self._reconnect_attempt) # Exponential backoff
        
        if not self._is_connected:
            logger.error("Failed to connect to WebSocket server after multiple attempts.")
            if self.on_error:
                GLib.idle_add(self.on_error, "Failed to connect to WebSocket server.")
            self.stop() # Stop the client if unable to connect

    async def _listen_for_messages(self):
        self._listener_running = True # Set flag to True
        try:
            while self._listener_running and self._websocket and self._websocket.state == websockets.client.State.OPEN: # Check if websocket is still active and open
                try:
                    message = await self._websocket.recv()
                    data = json.loads(message)
                    GLib.idle_add(self.on_message, data)
                except websockets.exceptions.ConnectionClosedOK:
                    logger.info("WebSocket listener stopped normally.")
                    self._listener_running = False
                except websockets.exceptions.ConnectionClosedError as e:
                    logger.warning(f"WebSocket listener connection error: {e}. Attempting to reconnect.")
                    self._listener_running = False
                    self._is_connected = False # Mark as disconnected to trigger reconnect
                    self._loop.call_soon_threadsafe(self._run_loop) # Attempt to reconnect
                except Exception as e:
                    logger.error(f"WebSocket listener error: {e}")
                    if self.on_error:
                        GLib.idle_add(self.on_error, str(e))
                    self._listener_running = False # Stop listener on unexpected error
        except Exception as e:
            logger.error(f"Error in WebSocket _listen_for_messages outer loop: {e}")
            self._listener_running = False
            if self.on_error:
                GLib.idle_add(self.on_error, str(e))
        finally:
            self._listener_running = False # Ensure flag is reset when loop exits

    def start(self):
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self.connect())

    def stop(self):
        if self._loop and not self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=1)  # Give it a moment to stop
        
        # Explicitly close websocket if it's open
        if self._websocket:
            asyncio.run_coroutine_threadsafe(self._websocket.close(), self._loop)

        self._websocket = None
        self._thread = None
        self._loop = None
        self._is_connected = False
        self._reconnect_attempt = 0
        self._listener_running = False

    async def send_request(self, request: dict):
        # Ensure connection is active before sending.
        # This will wait for connection if currently reconnecting, or try to establish.
        if not self._is_connected:
            logger.warning("WebSocket not connected. Attempting to reconnect before sending request.")
            # Start a new connection attempt in the background if not already connected
            # This logic might need refinement to avoid multiple connection attempts
            if not self._thread or not self._thread.is_alive():
                self.start()
            # Wait for connection to establish. This is a blocking wait in an async context
            # A more robust solution might involve a connection event or a queue.
            for _ in range(5): # Wait up to 5 seconds for connection
                if self._is_connected and self._websocket: # Removed _websocket.is_connected
                    break
                await asyncio.sleep(1)
            else:
                logger.error("Failed to re-establish WebSocket connection to send request.")
                if self.on_error:
                    GLib.idle_add(self.on_error, "WebSocket not connected to send request.")
                return

        if self._is_connected and self._websocket: # Removed _websocket.is_connected
            try:
                await self._websocket.send(json.dumps(request))
            except websockets.exceptions.ConnectionClosed:
                logger.warning("WebSocket connection closed during send. Will attempt to reconnect.")
                self._is_connected = False
                # Optionally, retry sending after a fresh connect attempt
                if self.on_error:
                    GLib.idle_add(self.on_error, "WebSocket connection lost during send.")
            except Exception as e:
                logger.error(f"Error sending WebSocket request: {e}")
                if self.on_error:
                    GLib.idle_add(self.on_error, f"Error sending request: {str(e)}")
        else:
            logger.warning("WebSocket not connected, request not sent (after retry logic).")
            if self.on_error:
                GLib.idle_add(self.on_error, "WebSocket not connected, request not sent.")

    async def get_history(
        self,
        offset: int,
        limit: int,
        sort_order: str,
        filters: Optional[Set[str]] = None,
    ):
        request = {
            "action": "get_history",
            "offset": offset,
            "limit": limit,
            "sort_order": sort_order,
        }
        if filters:
            request["filters"] = list(filters)
        await self.send_request(request)

    async def get_recently_pasted(
        self,
        offset: int,
        limit: int,
        sort_order: str,
        filters: Optional[Set[str]] = None,
    ):
        request = {
            "action": "get_recently_pasted",
            "offset": offset,
            "limit": limit,
            "sort_order": sort_order,
        }
        if filters:
            request["filters"] = list(filters)
        await self.send_request(request)

    async def search(self, query: str, limit: int, filters: Optional[Set[str]] = None):
        request = {"action": "search", "query": query, "limit": limit}
        if filters:
            request["filters"] = list(filters)
        await self.send_request(request)

    async def get_file_extensions(self):
        request = {"action": "get_file_extensions"}
        await self.send_request(request)
