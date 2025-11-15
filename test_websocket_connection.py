#!/usr/bin/env python3
"""Test WebSocket connection to server"""

import asyncio
import json

import websockets


async def test_websocket():
    uri = "ws://localhost:8765"
    print(f"Connecting to {uri}...")

    async with websockets.connect(uri) as websocket:
        print("✓ Connected!")

        # Request history
        request = {"action": "get_history", "limit": 10}
        await websocket.send(json.dumps(request))
        print("Requested history...")

        # Wait for response
        response = await websocket.recv()
        data = json.loads(response)

        if data.get("type") == "history":
            items = data.get("items", [])
            print(f"\n✓ Received {len(items)} items:")
            for item in items:
                item_type = item["type"]
                timestamp = item["timestamp"]
                if item_type == "text":
                    content = item["content"][:50]
                    print(f"  - [{timestamp}] Text: {content}")
                else:
                    print(f"  - [{timestamp}] {item_type}")

        print("\n✓ WebSocket test successful!")


if __name__ == "__main__":
    asyncio.run(test_websocket())
