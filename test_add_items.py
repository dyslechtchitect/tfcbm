#!/usr/bin/env python3
"""
Test script to add some clipboard items to the server
This simulates what the GNOME extension does
"""

import json
import os
import socket
from datetime import datetime

socket_path = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "simple-clipboard.sock")

# Test items to add
test_items = [
    {"type": "text", "content": "Hello, this is a test clipboard item!", "timestamp": datetime.now().isoformat()},
    {
        "type": "text",
        "content": "Another test item with some longer text to see how wrapping works in the UI",
        "timestamp": datetime.now().isoformat(),
    },
    {"type": "text", "content": "Short text", "timestamp": datetime.now().isoformat()},
]

print(f"Connecting to {socket_path}...")

for i, item in enumerate(test_items, 1):
    try:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.connect(socket_path)

        message = json.dumps(item) + "\n"
        client.sendall(message.encode("utf-8"))
        client.close()

        print(f"✓ Sent item {i}: {item['content'][:50]}")

    except Exception as e:
        print(f"✗ Error sending item {i}: {e}")

print("\nDone! Items should now appear in the server history.")
