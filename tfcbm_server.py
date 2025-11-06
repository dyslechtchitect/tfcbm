#!/usr/bin/env python3
"""
TFCBM Server - Receives clipboard data from GNOME Shell extension
"""

import socket
import os
import json
from datetime import datetime

history = []

def start_server():
    """Start UNIX socket server to receive clipboard data"""
    socket_path = os.path.join(os.environ.get('XDG_RUNTIME_DIR', '/tmp'), 'simple-clipboard.sock')

    # Remove existing socket if it exists
    try:
        os.unlink(socket_path)
    except FileNotFoundError:
        pass

    # Create UNIX socket
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(socket_path)
    server.listen(5)

    print(f"Listening on {socket_path}")
    print("Waiting for clipboard events from GNOME Shell extension...\n")

    try:
        while True:
            conn, _ = server.accept()
            try:
                data = conn.recv(4096).decode('utf-8')
                if data:
                    # Parse JSON message
                    message = json.loads(data.strip())

                    if message['type'] == 'text':
                        text = message['content']

                        # Check if it's new
                        is_new = not history or history[-1].get('content') != text

                        if is_new:
                            history.append({
                                'type': 'text',
                                'content': text,
                                'timestamp': datetime.now().isoformat(),
                            })

                            # Print what was copied
                            if len(text) > 100:
                                print(f"✓ Copied: {text[:100]}...")
                            else:
                                print(f"✓ Copied: {text}")
                            print(f"  (History: {len(history)} items)\n")

                    elif message['type'] == 'image':
                        # Handle image data (base64 encoded)
                        image_data = message['content']

                        history.append({
                            'type': 'image',
                            'content': image_data,
                            'timestamp': datetime.now().isoformat(),
                        })
                        print(f"✓ Copied image ({len(image_data)} bytes)")
                        print(f"  (History: {len(history)} items)\n")

            except json.JSONDecodeError:
                pass
            finally:
                conn.close()

    except KeyboardInterrupt:
        print("\nStopping server...")
        print(f"Total items saved: {len(history)}")
    finally:
        server.close()
        os.unlink(socket_path)

if __name__ == '__main__':
    start_server()
