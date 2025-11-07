#!/usr/bin/env python3
"""
TFCBM Server - Receives clipboard data from GNOME Shell extension
"""

import socket
import os
import json
import threading
import time
import subprocess
import base64
from datetime import datetime
from pathlib import Path

history = []

# Screenshot configuration
SCREENSHOT_INTERVAL = 30  # seconds between screenshots
SCREENSHOT_ENABLED = True  # Set to False to disable automatic screenshots
SCREENSHOT_SAVE_DIR = None  # Set to a directory path to save screenshots to disk (e.g., './screenshots')

def capture_screenshot():
    """Capture a full-screen screenshot using grim (Wayland screenshot tool)"""
    try:
        # Create temporary file for screenshot
        temp_file = f"/tmp/tfcbm_screenshot_{int(time.time())}.png"

        # Capture screenshot using grim (Wayland-native tool)
        result = subprocess.run(
            ['grim', temp_file],
            capture_output=True,
            timeout=5
        )

        if result.returncode == 0 and os.path.exists(temp_file):
            # Read screenshot and encode as base64
            with open(temp_file, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')

            # Clean up temp file
            os.remove(temp_file)

            return image_data
        else:
            print(f"⚠ Screenshot capture failed: {result.stderr.decode() if result.stderr else 'Unknown error'}")
            return None

    except subprocess.TimeoutExpired:
        print("⚠ Screenshot capture timed out")
        return None
    except Exception as e:
        print(f"⚠ Screenshot error: {e}")
        return None

def screenshot_worker():
    """Background thread that captures screenshots at regular intervals"""
    print(f"📸 Screenshot capture started (interval: {SCREENSHOT_INTERVAL}s)")

    # Create screenshot save directory if specified
    if SCREENSHOT_SAVE_DIR:
        Path(SCREENSHOT_SAVE_DIR).mkdir(parents=True, exist_ok=True)
        print(f"📁 Saving screenshots to: {SCREENSHOT_SAVE_DIR}")

    while SCREENSHOT_ENABLED:
        try:
            time.sleep(SCREENSHOT_INTERVAL)

            # Capture screenshot
            image_data = capture_screenshot()

            if image_data:
                timestamp = datetime.now()
                timestamp_str = timestamp.isoformat()

                # Add to history
                history.append({
                    'type': 'screenshot',
                    'content': image_data,
                    'timestamp': timestamp_str,
                })

                # Optionally save to disk
                if SCREENSHOT_SAVE_DIR:
                    filename = f"screenshot_{timestamp.strftime('%Y%m%d_%H%M%S')}.png"
                    filepath = Path(SCREENSHOT_SAVE_DIR) / filename

                    # Decode base64 and save
                    with open(filepath, 'wb') as f:
                        f.write(base64.b64decode(image_data))

                    print(f"📸 Screenshot captured and saved: {filename}")
                else:
                    print(f"📸 Screenshot captured ({len(image_data)} bytes)")

                print(f"  (History: {len(history)} items)\n")

        except Exception as e:
            print(f"⚠ Screenshot worker error: {e}")

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

    # Start screenshot capture thread
    if SCREENSHOT_ENABLED:
        screenshot_thread = threading.Thread(target=screenshot_worker, daemon=True)
        screenshot_thread.start()

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
