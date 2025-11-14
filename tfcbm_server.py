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
import asyncio
import websockets
from datetime import datetime
from pathlib import Path
from io import BytesIO
from PIL import Image
from database import ClipboardDB
from concurrent.futures import ThreadPoolExecutor

# Initialize database
db = ClipboardDB()
print(f"Database initialized at: {db.db_path}")

history = []  # Keep in-memory for legacy compatibility

# WebSocket clients
ws_clients = set()
last_known_id = db.get_latest_id() or 0
db_lock = threading.Lock()  # Lock for thread-safe database access

# Thread pool for thumbnail generation
thumbnail_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix='thumbnail')

def generate_thumbnail(image_data: bytes, max_size: int = 250) -> bytes:
    """
    Generate a thumbnail from image data

    Args:
        image_data: Original image bytes
        max_size: Maximum width/height (maintains aspect ratio)

    Returns:
        Thumbnail image bytes (PNG format)
    """
    try:
        # Open image from bytes
        image = Image.open(BytesIO(image_data))

        # Convert RGBA to RGB if needed (for JPEG compatibility)
        if image.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P':
                image = image.convert('RGBA')
            background.paste(image, mask=image.split()[-1] if image.mode in ('RGBA', 'LA') else None)
            image = background

        # Calculate thumbnail size maintaining aspect ratio
        image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

        # Save to bytes
        thumbnail_io = BytesIO()
        image.save(thumbnail_io, format='PNG', optimize=True)
        thumbnail_bytes = thumbnail_io.getvalue()

        print(f"  Generated thumbnail: {image.size} -> {len(thumbnail_bytes)} bytes")
        return thumbnail_bytes

    except Exception as e:
        print(f"  Error generating thumbnail: {e}")
        return None


def process_thumbnail_async(item_id: int, image_data: bytes):
    """
    Process thumbnail in background thread

    Args:
        item_id: Database item ID
        image_data: Original image bytes
    """
    def worker():
        try:
            thumbnail = generate_thumbnail(image_data)
            if thumbnail:
                with db_lock:
                    db.update_thumbnail(item_id, thumbnail)
                print(f"  ✓ Thumbnail saved for item {item_id}")
        except Exception as e:
            print(f"  Error in thumbnail worker: {e}")

    # Submit to thread pool
    thumbnail_executor.submit(worker)

# Screenshot configuration
SCREENSHOT_INTERVAL = 30  # seconds between screenshots
SCREENSHOT_ENABLED = False  # Set to False to disable automatic screenshots
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

                # Add to history (in-memory)
                history.append({
                    'type': 'screenshot',
                    'content': image_data,
                    'timestamp': timestamp_str,
                })

                # Save to database (thread-safe)
                image_bytes = base64.b64decode(image_data)
                with db_lock:
                    item_id = db.add_item('screenshot', image_bytes, timestamp_str)

                # Generate thumbnail asynchronously
                process_thumbnail_async(item_id, image_bytes)

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

def prepare_item_for_ui(item: dict) -> dict:
    """Convert database item to UI-renderable format"""
    item_type = item['type']
    data = item['data']
    thumbnail = item.get('thumbnail')

    if item_type == 'text':
        content = data.decode('utf-8') if isinstance(data, bytes) else data
        thumbnail_b64 = None
    elif item_type.startswith('image/') or item_type == 'screenshot':
        # DON'T send full image in WebSocket messages - too large!
        # Only send item ID and thumbnail
        content = None  # Client will request full image only when saving
        # Use thumbnail if available, generate one if not
        if thumbnail:
            thumbnail_b64 = base64.b64encode(thumbnail).decode('utf-8')
        else:
            # No thumbnail yet - generate a placeholder or small version
            try:
                # Try to generate thumbnail on-the-fly for old items
                thumb = generate_thumbnail(data, max_size=250)
                if thumb:
                    thumbnail_b64 = base64.b64encode(thumb).decode('utf-8')
                    # Update database with generated thumbnail
                    with db_lock:
                        db.update_thumbnail(item['id'], thumb)
                else:
                    thumbnail_b64 = None
            except:
                thumbnail_b64 = None
    else:
        try:
            content = data.decode('utf-8') if isinstance(data, bytes) else data
        except:
            content = base64.b64encode(data).decode('utf-8') if isinstance(data, bytes) else data
        thumbnail_b64 = None

    return {
        'id': item['id'],
        'type': item_type,
        'content': content,  # None for images
        'thumbnail': thumbnail_b64,
        'timestamp': item['timestamp']
    }


async def websocket_handler(websocket):
    """Handle WebSocket client connections from UI"""
    global ws_clients, last_known_id

    print(f"WebSocket client connected from {websocket.remote_address}")
    ws_clients.add(websocket)

    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                action = data.get('action')

                if action == 'get_history':
                    limit = data.get('limit', 100)

                    # Use lock for thread-safe database access
                    with db_lock:
                        items = db.get_items(limit=limit)

                    # Convert to UI format
                    ui_items = [prepare_item_for_ui(item) for item in items]

                    response = {
                        'type': 'history',
                        'items': ui_items
                    }
                    await websocket.send(json.dumps(response))

                elif action == 'get_full_image':
                    # Get full image data for saving
                    item_id = data.get('id')
                    if item_id:
                        with db_lock:
                            item = db.get_item(item_id)
                        if item and (item['type'].startswith('image/') or item['type'] == 'screenshot'):
                            full_image_b64 = base64.b64encode(item['data']).decode('utf-8')
                            response = {
                                'type': 'full_image',
                                'id': item_id,
                                'content': full_image_b64
                            }
                            await websocket.send(json.dumps(response))

                elif action == 'delete_item':
                    item_id = data.get('id')
                    if item_id:
                        with db_lock:
                            db.delete_item(item_id)
                        # Notify all clients
                        await broadcast_ws({
                            'type': 'item_deleted',
                            'id': item_id
                        })

            except Exception as e:
                print(f"Error handling WebSocket message: {e}")
                import traceback
                traceback.print_exc()

    except websockets.exceptions.ConnectionClosed:
        pass
    except Exception as e:
        print(f"WebSocket handler error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        ws_clients.remove(websocket)
        print(f"WebSocket client disconnected")


async def broadcast_ws(message: dict):
    """Broadcast message to all WebSocket clients"""
    if ws_clients:
        message_json = json.dumps(message)
        await asyncio.gather(
            *[client.send(message_json) for client in ws_clients],
            return_exceptions=True
        )


def watch_for_new_items(loop):
    """Background thread to watch for new database items and broadcast to WebSocket clients"""
    global last_known_id

    print("Starting database watcher for WebSocket broadcasts...")

    while True:
        try:
            with db_lock:
                latest_id = db.get_latest_id()

            if latest_id and latest_id > last_known_id:
                # New items detected
                for item_id in range(last_known_id + 1, latest_id + 1):
                    with db_lock:
                        item = db.get_item(item_id)
                    if item:
                        ui_item = prepare_item_for_ui(item)

                        # Broadcast to all clients
                        message = {
                            'type': 'new_item',
                            'item': ui_item
                        }

                        # Schedule broadcast in async loop
                        asyncio.run_coroutine_threadsafe(
                            broadcast_ws(message),
                            loop
                        )

                last_known_id = latest_id

        except Exception as e:
            print(f"Error in database watcher: {e}")

        time.sleep(0.5)


async def start_websocket_server():
    """Start WebSocket server for UI"""
    print("Starting WebSocket server on ws://localhost:8765")
    async with websockets.serve(websocket_handler, 'localhost', 8765):
        await asyncio.Future()  # Run forever


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

    # Start WebSocket server in separate thread with its own event loop
    def run_websocket_server():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Start database watcher
        watcher_thread = threading.Thread(target=watch_for_new_items, args=(loop,), daemon=True)
        watcher_thread.start()

        # Start WebSocket server
        loop.run_until_complete(start_websocket_server())

    websocket_thread = threading.Thread(target=run_websocket_server, daemon=True)
    websocket_thread.start()
    print("WebSocket server started\n")

    try:
        while True:
            conn, _ = server.accept()
            try:
                # Read data until we get a newline (for JSON messages)
                full_data = b''
                while b'\n' not in full_data:
                    data = conn.recv(4096)
                    if not data:
                        break
                    full_data += data

                if full_data:
                    message = json.loads(full_data.decode('utf-8').strip())

                    # Handle UI requests
                    if 'action' in message:
                        if message['action'] == 'get_history':
                            try:
                                response = json.dumps({'history': history}) + '\n'
                                conn.sendall(response.encode('utf-8'))
                            except BrokenPipeError:
                                pass  # Client disconnected
                        # Don't close connection yet - let client close it
                        continue

                    # Handle clipboard events from extension
                    if message['type'] == 'text':
                        text = message['content']

                        # Check if it's new
                        is_new = not history or history[-1].get('content') != text

                        if is_new:
                            timestamp = datetime.now().isoformat()

                            history.append({
                                'type': 'text',
                                'content': text,
                                'timestamp': timestamp,
                            })

                            # Save to database (thread-safe)
                            with db_lock:
                                db.add_item('text', text.encode('utf-8'), timestamp)

                            # Print what was copied
                            if len(text) > 100:
                                print(f"✓ Copied: {text[:100]}...")
                            else:
                                print(f"✓ Copied: {text}")
                            print(f"  (History: {len(history)} items)\n")

                    elif message['type'].startswith('image/'):
                        # Handle image data (base64 encoded)
                        image_content = json.loads(message['content'])
                        image_data = image_content['data']
                        timestamp = datetime.now().isoformat()

                        history.append({
                            'type': message['type'],
                            'content': image_data,
                            'timestamp': timestamp,
                        })

                        # Save to database (thread-safe)
                        image_bytes = base64.b64decode(image_data)
                        with db_lock:
                            item_id = db.add_item(message['type'], image_bytes, timestamp)

                        # Generate thumbnail asynchronously
                        process_thumbnail_async(item_id, image_bytes)

                        print(f"✓ Copied image ({message['type']}) ({len(image_data)} bytes)")
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
