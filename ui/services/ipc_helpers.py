"""Helper functions for IPC communication - replaces websockets.connect()"""

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

logger = logging.getLogger("TFCBM.IPC.Helpers")


class IPCConnection:
    """Context manager for one-off IPC connections (replaces websockets.connect)"""

    def __init__(self, socket_path: Optional[str] = None):
        self.socket_path = socket_path or self._get_default_socket_path()
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None

    def _get_default_socket_path(self) -> str:
        """Get the default UNIX socket path."""
        runtime_dir = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
        return os.path.join(runtime_dir, "tfcbm-ipc.sock")

    async def __aenter__(self):
        """Connect to IPC server"""
        self._reader, self._writer = await asyncio.open_unix_connection(self.socket_path)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close IPC connection"""
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()

    def __aiter__(self):
        """Make connection async iterable"""
        return self

    async def __anext__(self) -> str:
        """Receive next message in async iteration"""
        try:
            return await self.recv()
        except (ConnectionError, asyncio.IncompleteReadError) as e:
            logger.debug(f"Stopping async iteration due to: {type(e).__name__}: {e}")
            raise StopAsyncIteration
        except Exception as e:
            logger.error(f"Unexpected error in async iteration: {type(e).__name__}: {e}")
            raise

    async def send(self, message: str):
        """Send a JSON string message"""
        if not self._writer or self._writer.is_closing():
            raise ConnectionError("IPC connection is closed")

        message_bytes = message.encode('utf-8') + b'\n'
        length_prefix = f"{len(message_bytes)}\n".encode('utf-8')
        self._writer.write(length_prefix + message_bytes)
        await self._writer.drain()

    async def recv(self) -> str:
        """Receive a JSON string message"""
        if not self._reader or self._reader.at_eof():
            raise ConnectionClosedError("IPC connection is closed")

        # Read length prefix
        length_line = await self._reader.readuntil(b'\n')
        message_length = int(length_line.decode('utf-8').strip())

        # Read message
        message_bytes = await self._reader.readexactly(message_length)
        return message_bytes.decode('utf-8').rstrip('\n')


@asynccontextmanager
async def connect(uri: str = None, max_size: int = None, ping_timeout: int = None, open_timeout: int = None):
    """
    Drop-in replacement for websockets.connect()

    Args:
        uri: Ignored (for compatibility) - uses UNIX socket instead
        max_size: Ignored (for compatibility)
        ping_timeout: Ignored (for compatibility)
        open_timeout: Ignored (for compatibility)

    Yields:
        IPCConnection object with send/recv methods
    """
    # Ignore all WebSocket-specific parameters
    conn = IPCConnection()
    async with conn as connection:
        yield connection


# Exceptions for compatibility with websockets library
class ConnectionClosedError(Exception):
    """Raised when connection is closed unexpectedly"""
    pass


class ConnectionClosedOK(Exception):
    """Raised when connection is closed normally"""
    pass


class ConnectionClosed(Exception):
    """Base exception for connection closures"""
    pass


# Create a namespace object to mimic websockets.exceptions
class _Exceptions:
    ConnectionClosedError = ConnectionClosedError
    ConnectionClosedOK = ConnectionClosedOK
    ConnectionClosed = ConnectionClosed


# Create a namespace object to mimic websockets module structure
class _WebSocketsCompat:
    connect = connect
    exceptions = _Exceptions()

    # For websocket.state checks (compatibility)
    class client:
        class State:
            OPEN = 1
            CLOSING = 2
            CLOSED = 3


# Export the compatibility object
websockets_compat = _WebSocketsCompat()
