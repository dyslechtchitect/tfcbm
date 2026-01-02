"""UNIX domain socket IPC client for TFCBM backend communication."""

import asyncio
import json
import logging
import os
import threading
from typing import Callable, Optional, Set

from gi.repository import GLib

logger = logging.getLogger("TFCBM.IPCClient")


class IPCClient:
    """UNIX domain socket client for IPC with backend server."""

    def __init__(
        self,
        socket_path: Optional[str] = None,
        on_message: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
    ):
        self.socket_path = socket_path or self._get_default_socket_path()
        self.on_message = on_message
        self.on_error = on_error
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._thread = None
        self._loop = None
        self._is_connected = False
        self._reconnect_attempt = 0
        self._listener_running = False

    def _get_default_socket_path(self) -> str:
        """Get the default UNIX socket path."""
        runtime_dir = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
        return os.path.join(runtime_dir, "tfcbm-ipc.sock")

    async def connect(self):
        """Connect to the IPC server."""
        self._is_connected = False
        self._reconnect_attempt = 0

        while not self._is_connected and self._reconnect_attempt < 5:  # Retry 5 times
            try:
                logger.info(f"Connecting to IPC server at {self.socket_path} (attempt {self._reconnect_attempt + 1})...")
                self._reader, self._writer = await asyncio.wait_for(
                    asyncio.open_unix_connection(self.socket_path),
                    timeout=5.0
                )
                self._is_connected = True
                logger.info("Connected to IPC server")

                # Register UI PID with server for cleanup
                await self._register_ui_pid()

                await self._listen_for_messages()
            except asyncio.TimeoutError:
                logger.warning(f"Connection timeout. Retrying...")
                self._is_connected = False
                self._reconnect_attempt += 1
                await asyncio.sleep(2 ** self._reconnect_attempt)  # Exponential backoff
            except FileNotFoundError:
                logger.warning(f"Socket file not found: {self.socket_path}. Retrying...")
                self._is_connected = False
                self._reconnect_attempt += 1
                await asyncio.sleep(2 ** self._reconnect_attempt)
            except Exception as e:
                self._is_connected = False
                self._reconnect_attempt += 1
                logger.warning(f"IPC connection failed: {e}. Retrying in {2 ** self._reconnect_attempt} seconds...")
                await asyncio.sleep(2 ** self._reconnect_attempt)  # Exponential backoff

        if not self._is_connected:
            logger.error("Failed to connect to IPC server after multiple attempts.")
            if self.on_error:
                GLib.idle_add(self.on_error, "Failed to connect to IPC server.")
            self.stop()  # Stop the client if unable to connect

    async def _register_ui_pid(self):
        """Register UI process PID with server for cleanup when server exits"""
        try:
            ui_pid = os.getpid()
            request = {"action": "register_ui_pid", "pid": ui_pid}
            await self.send_request(request)
            logger.info(f"Registered UI PID {ui_pid} with server")
        except Exception as e:
            logger.error(f"Failed to register UI PID: {e}")

    async def _receive_message(self) -> Optional[dict]:
        """Receive a JSON message with length prefix."""
        if not self._reader or self._reader.at_eof():
            return None

        try:
            # Read length prefix
            length_line = await self._reader.readuntil(b'\n')
            message_length = int(length_line.decode('utf-8').strip())

            # Read message
            message_bytes = await self._reader.readexactly(message_length)
            message_str = message_bytes.decode('utf-8').rstrip('\n')
            return json.loads(message_str)
        except asyncio.IncompleteReadError:
            # Connection closed
            return None
        except Exception as e:
            logger.error(f"Error receiving message: {e}")
            return None

    async def _send_message(self, data: dict):
        """Send a JSON message with length prefix."""
        if not self._writer or self._writer.is_closing():
            raise ConnectionError("IPC connection is closed")

        try:
            json_str = json.dumps(data)
            message_bytes = json_str.encode('utf-8') + b'\n'
            # Send length prefix followed by message
            length_prefix = f"{len(message_bytes)}\n".encode('utf-8')
            self._writer.write(length_prefix + message_bytes)
            await self._writer.drain()
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            raise

    async def _listen_for_messages(self):
        """Listen for incoming messages from the server."""
        self._listener_running = True
        try:
            while self._listener_running and self._is_connected:
                try:
                    message = await self._receive_message()
                    if message is None:
                        logger.info("IPC connection closed by server")
                        self._listener_running = False
                        self._is_connected = False
                        break

                    if self.on_message:
                        GLib.idle_add(self.on_message, message)
                except Exception as e:
                    logger.error(f"IPC listener error: {e}")
                    if self.on_error:
                        GLib.idle_add(self.on_error, str(e))
                    self._listener_running = False
        except Exception as e:
            logger.error(f"Error in IPC _listen_for_messages outer loop: {e}")
            self._listener_running = False
            if self.on_error:
                GLib.idle_add(self.on_error, str(e))
        finally:
            self._listener_running = False

    def start(self):
        """Start the IPC client in a background thread."""
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()

    def _run_loop(self):
        """Run the asyncio event loop."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self.connect())

    def stop(self):
        """Stop the IPC client."""
        self._listener_running = False

        if self._writer and not self._writer.is_closing():
            try:
                self._writer.close()
                if self._loop and self._loop.is_running():
                    asyncio.run_coroutine_threadsafe(self._writer.wait_closed(), self._loop)
            except Exception as e:
                logger.error(f"Error closing writer: {e}")

        if self._loop and self._loop.is_running():
            try:
                self._loop.call_soon_threadsafe(self._loop.stop)
            except Exception:
                pass

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1)

        self._reader = None
        self._writer = None
        self._thread = None
        self._loop = None
        self._is_connected = False
        self._reconnect_attempt = 0

    async def send_request(self, request: dict):
        """Send a request to the server."""
        # Ensure connection is active before sending
        if not self._is_connected:
            logger.warning("IPC not connected. Attempting to reconnect before sending request.")
            if not self._thread or not self._thread.is_alive():
                self.start()
            # Wait for connection to establish
            for _ in range(5):  # Wait up to 5 seconds for connection
                if self._is_connected and self._writer:
                    break
                await asyncio.sleep(1)
            else:
                logger.error("Failed to re-establish IPC connection to send request.")
                if self.on_error:
                    GLib.idle_add(self.on_error, "IPC not connected to send request.")
                return

        if self._is_connected and self._writer:
            try:
                await self._send_message(request)
            except ConnectionError:
                logger.warning("IPC connection closed during send. Will attempt to reconnect.")
                self._is_connected = False
                if self.on_error:
                    GLib.idle_add(self.on_error, "IPC connection lost during send.")
            except Exception as e:
                logger.error(f"Error sending IPC request: {e}")
                if self.on_error:
                    GLib.idle_add(self.on_error, f"Error sending request: {str(e)}")
        else:
            logger.warning("IPC not connected, request not sent (after retry logic).")
            if self.on_error:
                GLib.idle_add(self.on_error, "IPC not connected, request not sent.")

    async def get_history(
        self,
        offset: int,
        limit: int,
        sort_order: str,
        filters: Optional[Set[str]] = None,
    ):
        """Request clipboard history from server."""
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
        """Request recently pasted items from server."""
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
        """Search clipboard items."""
        request = {"action": "search", "query": query, "limit": limit}
        if filters:
            request["filters"] = list(filters)
        await self.send_request(request)

    async def get_file_extensions(self):
        """Get available file extensions."""
        request = {"action": "get_file_extensions"}
        await self.send_request(request)
