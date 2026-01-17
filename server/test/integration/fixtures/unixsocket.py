"""UNIX socket fixtures and mocks for tests."""

import asyncio
import json
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock


class FakeStreamReader:
    """Fake asyncio.StreamReader for testing."""

    def __init__(self):
        self.messages: List[bytes] = []
        self.closed = False

    async def read(self, n: int = -1) -> bytes:
        """Simulate reading from stream."""
        if not self.messages:
            await asyncio.sleep(0.1)
            if not self.messages:
                return b''
        return self.messages.pop(0)

    async def readline(self) -> bytes:
        """Simulate reading a line from stream."""
        if not self.messages:
            await asyncio.sleep(0.1)
            if not self.messages:
                return b''
        return self.messages.pop(0)

    async def readuntil(self, separator: bytes = b'\n') -> bytes:
        """Simulate reading until separator."""
        if not self.messages:
            await asyncio.sleep(0.1)
            if not self.messages:
                raise asyncio.IncompleteReadError(b'', None)
        return self.messages.pop(0)

    def add_message(self, message: bytes):
        """Add a message to the read queue."""
        self.messages.append(message)

    def at_eof(self) -> bool:
        """Check if stream is at EOF."""
        return self.closed and len(self.messages) == 0


class FakeStreamWriter:
    """Fake asyncio.StreamWriter for testing."""

    def __init__(self):
        self.written_data: List[bytes] = []
        self.closed = False

    def write(self, data: bytes):
        """Simulate writing to stream."""
        if not self.closed:
            self.written_data.append(data)

    async def drain(self):
        """Simulate draining write buffer."""
        await asyncio.sleep(0)

    def close(self):
        """Close the writer."""
        self.closed = True

    async def wait_closed(self):
        """Wait for the writer to close."""
        await asyncio.sleep(0)

    def get_written_messages(self) -> List[bytes]:
        """Get all written data."""
        return self.written_data

    def get_written_json(self, index: int = -1) -> Dict[str, Any]:
        """Get a written message as parsed JSON."""
        data = self.written_data[index]
        # Remove length prefix and newline
        message = data.split(b'\n', 1)[1] if b'\n' in data else data
        return json.loads(message.decode('utf-8').rstrip('\n'))

    def get_all_written_json(self) -> List[Dict[str, Any]]:
        """Get all written messages as parsed JSON."""
        result = []
        for data in self.written_data:
            # Remove length prefix and newline
            message = data.split(b'\n', 1)[1] if b'\n' in data else data
            try:
                result.append(json.loads(message.decode('utf-8').rstrip('\n')))
            except json.JSONDecodeError:
                continue
        return result


class FakeUnixSocket:
    """Fake UNIX socket connection for testing (combines reader and writer)."""

    def __init__(self):
        self.reader = FakeStreamReader()
        self.writer = FakeStreamWriter()
        self.remote_address = "fake_unix_socket"

    def add_received_message(self, message: Dict[str, Any]):
        """Add a message to the receive queue."""
        json_str = json.dumps(message)
        message_bytes = json_str.encode('utf-8') + b'\n'
        # Add length prefix
        length_prefix = f"{len(message_bytes)}\n".encode('utf-8')
        self.reader.add_message(length_prefix + message_bytes)

    async def send_json(self, data: Dict[str, Any]):
        """Send a JSON message."""
        json_str = json.dumps(data)
        message_bytes = json_str.encode('utf-8') + b'\n'
        # Add length prefix
        length_prefix = f"{len(message_bytes)}\n".encode('utf-8')
        self.writer.write(length_prefix + message_bytes)
        await self.writer.drain()

    async def close(self):
        """Close the connection."""
        self.writer.close()
        await self.writer.wait_closed()
        self.reader.closed = True


class FakeUnixSocketServer:
    """Fake UNIX socket server for testing."""

    def __init__(self):
        self.clients: List[FakeUnixSocket] = []
        self.started = False
        self.socket_path: Optional[str] = None

    async def start(self, socket_path: str):
        """Start the server."""
        self.started = True
        self.socket_path = socket_path

    def add_client(self) -> FakeUnixSocket:
        """Add a new client connection."""
        client = FakeUnixSocket()
        self.clients.append(client)
        return client

    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast a message to all clients."""
        for client in self.clients:
            await client.send_json(message)

    async def stop(self):
        """Stop the server."""
        for client in self.clients:
            await client.close()
        self.started = False
        self.clients.clear()


def create_socket_message(action: str, **data) -> Dict[str, Any]:
    """Create a socket message dictionary."""
    message = {"action": action, **data}
    return message
