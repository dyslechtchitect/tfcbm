"""WebSocket fixtures and mocks for tests."""

import asyncio
import json
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock


class FakeWebSocket:
    """Fake WebSocket client for testing."""

    def __init__(self):
        self.sent_messages: List[str] = []
        self.received_messages: List[str] = []
        self.closed = False

    async def send(self, message: str):
        """Simulate sending a message."""
        self.sent_messages.append(message)

    async def recv(self) -> str:
        """Simulate receiving a message."""
        if not self.received_messages:
            # Wait indefinitely or until a message is added
            await asyncio.sleep(0.1)
            if not self.received_messages:
                raise asyncio.CancelledError("No messages to receive")
        return self.received_messages.pop(0)

    def add_received_message(self, message: str):
        """Add a message to the receive queue."""
        self.received_messages.append(message)

    async def close(self):
        """Close the connection."""
        self.closed = True

    def get_sent_json(self, index: int = -1) -> Dict[str, Any]:
        """Get a sent message as parsed JSON."""
        return json.loads(self.sent_messages[index])

    def get_all_sent_json(self) -> List[Dict[str, Any]]:
        """Get all sent messages as parsed JSON."""
        return [json.loads(msg) for msg in self.sent_messages]


class FakeWebSocketServer:
    """Fake WebSocket server for testing."""

    def __init__(self):
        self.clients: List[FakeWebSocket] = []
        self.started = False
        self.port: Optional[int] = None

    async def start(self, port: int):
        """Start the server."""
        self.started = True
        self.port = port

    def add_client(self) -> FakeWebSocket:
        """Add a new client connection."""
        client = FakeWebSocket()
        self.clients.append(client)
        return client

    async def broadcast(self, message: str):
        """Broadcast a message to all clients."""
        for client in self.clients:
            await client.send(message)

    async def stop(self):
        """Stop the server."""
        for client in self.clients:
            await client.close()
        self.started = False
        self.clients.clear()


def create_websocket_message(action: str, **data) -> str:
    """Create a WebSocket message JSON string."""
    message = {"action": action, **data}
    return json.dumps(message)
