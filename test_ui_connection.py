#!/usr/bin/env python3
"""Test UI connection to server"""

import json
import os
import socket

socket_path = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "simple-clipboard.sock")

print(f"Connecting to {socket_path}...")

try:
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.connect(socket_path)

    print("Connected! Requesting history...")

    request = json.dumps({"action": "get_history"}) + "\n"
    client.sendall(request.encode("utf-8"))

    response_data = b""
    while True:
        chunk = client.recv(4096)
        if not chunk:
            break
        response_data += chunk

    client.close()

    response = json.loads(response_data.decode("utf-8").strip())
    history = response.get("history", [])

    print(f"\nReceived {len(history)} items:")
    for i, item in enumerate(history[-5:]):  # Show last 5
        item_type = item.get("type", "unknown")
        timestamp = item.get("timestamp", "")
        if item_type == "text":
            content = item.get("content", "")[:50]
            print(f"  {i + 1}. [{timestamp}] Text: {content}...")
        else:
            print(f"  {i + 1}. [{timestamp}] {item_type}")

    print("\n✓ Connection test successful!")

except Exception as e:
    print(f"✗ Error: {e}")
