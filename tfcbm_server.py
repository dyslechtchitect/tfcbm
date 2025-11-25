#!/usr/bin/env python3
"""
TFCBM Server - Receives clipboard data from GNOME Shell extension
"""

import asyncio
import base64
import json
import logging
import mimetypes
import os
import re
import socket
import subprocess
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from io import BytesIO
from pathlib import Path
from urllib.parse import unquote, urlparse

import websockets
from PIL import Image

from database import ClipboardDB
from settings import get_settings

# Configure logging with module name
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Initialize settings
settings = get_settings()

# Initialize database
db = ClipboardDB()
logging.info(f"Database initialized at: {db.db_path}")

history = []  # Keep in-memory for legacy compatibility

# WebSocket clients
ws_clients = set()
last_known_id = db.get_latest_id() or 0
db_lock = threading.Lock()  # Lock for thread-safe database access

# Thread pool for thumbnail generation
thumbnail_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="thumbnail")


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
        if image.mode in ("RGBA", "LA", "P"):
            background = Image.new("RGB", image.size, (255, 255, 255))
            if image.mode == "P":
                image = image.convert("RGBA")
            background.paste(image, mask=image.split()[-1] if image.mode in ("RGBA", "LA") else None)
            image = background

        # Calculate thumbnail size maintaining aspect ratio
        image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

        # Save to bytes
        thumbnail_io = BytesIO()
        image.save(thumbnail_io, format="PNG", optimize=True)
        thumbnail_bytes = thumbnail_io.getvalue()

        logging.info(f"Generated thumbnail: {image.size} -> {len(thumbnail_bytes)} bytes")
        return thumbnail_bytes

    except Exception as e:
        logging.error(f"Error generating thumbnail: {e}")
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
                logging.info(f"✓ Thumbnail saved for item {item_id}")
        except Exception as e:
            logging.error(f"Error in thumbnail worker: {e}")

    # Submit to thread pool
    thumbnail_executor.submit(worker)


def process_file(file_uri: str) -> dict:
    """
    Process a file URI and read its contents

    Args:
        file_uri: file:// URI from clipboard

    Returns:
        Dict with file metadata and content, or None if error
    """
    try:
        # Parse file URI to get path
        parsed = urlparse(file_uri)
        file_path = unquote(parsed.path)

        # Check if path exists
        path_obj = Path(file_path)
        if not path_obj.exists():
            logging.error(f"Path not found: {file_path}")
            return None

        # Handle directories
        if path_obj.is_dir():
            folder_name = path_obj.name
            # For directories, we don't store content, just metadata
            metadata = {
                'name': folder_name,
                'size': 0,  # Folders don't have a size we can easily calculate
                'mime_type': 'inode/directory',
                'extension': '',  # Folders don't have extensions
                'original_path': file_path,
                'is_directory': True,
            }
            logging.info(f"Processed folder: {folder_name}")
            return {
                'metadata': metadata,
                'content': b''  # Empty content for folders
            }

        # Handle regular files
        if not path_obj.is_file():
            logging.error(f"Not a file or directory: {file_path}")
            return None

        # Get file info
        file_name = path_obj.name
        file_size = path_obj.stat().st_size

        # Extract file extension (handle dotfiles better)
        # For files like ".zshrc", treat the whole name as the extension
        file_extension = path_obj.suffix.lower()
        if not file_extension and file_name.startswith('.') and file_name.count('.') == 1:
            # Dotfile without extension (e.g., .zshrc, .bashrc)
            file_extension = file_name.lower()
        elif not file_extension and '.' in file_name:
            # File with extension but no stem (shouldn't happen normally)
            file_extension = '.' + file_name.split('.')[-1].lower()

        # Determine mime type
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = "application/octet-stream"

        # Read file contents (with size limit for safety)
        MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB limit
        if file_size > MAX_FILE_SIZE:
            logging.warning(f"File too large: {file_size} bytes (max: {MAX_FILE_SIZE})")
            return None

        with open(file_path, 'rb') as f:
            file_content = f.read()

        # Create metadata JSON
        metadata = {
            'name': file_name,
            'size': file_size,
            'mime_type': mime_type,
            'extension': file_extension,
            'original_path': file_path,
            'is_directory': False,
        }

        logging.info(f"Processed file: {file_name} ({file_size} bytes, {mime_type})")

        return {
            'metadata': metadata,
            'content': file_content
        }

    except Exception as e:
        logging.error(f"Error processing file {file_uri}: {e}")
        return None


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
        result = subprocess.run(["grim", temp_file], capture_output=True, timeout=5)

        if result.returncode == 0 and os.path.exists(temp_file):
            # Read screenshot and encode as base64
            with open(temp_file, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")

            # Clean up temp file
            os.remove(temp_file)

            return image_data
        else:
            logging.warning(
                f"Screenshot capture failed: {result.stderr.decode() if result.stderr else 'Unknown error'}"
            )
            return None

    except subprocess.TimeoutExpired:
        logging.warning("Screenshot capture timed out")
        return None
    except Exception as e:
        logging.error(f"Screenshot error: {e}")
        return None


def screenshot_worker():
    """Background thread that captures screenshots at regular intervals"""
    logging.info(f"📸 Screenshot capture started (interval: {SCREENSHOT_INTERVAL}s)")

    # Create screenshot save directory if specified
    if SCREENSHOT_SAVE_DIR:
        Path(SCREENSHOT_SAVE_DIR).mkdir(parents=True, exist_ok=True)
        logging.info(f"📁 Saving screenshots to: {SCREENSHOT_SAVE_DIR}")

    while SCREENSHOT_ENABLED:
        try:
            time.sleep(SCREENSHOT_INTERVAL)

            # Capture screenshot
            image_data = capture_screenshot()

            if image_data:
                timestamp = datetime.now()
                timestamp_str = timestamp.isoformat()

                # Add to history (in-memory)
                history.append(
                    {
                        "type": "screenshot",
                        "content": image_data,
                        "timestamp": timestamp_str,
                    }
                )

                # Save to database (thread-safe)
                image_bytes = base64.b64decode(image_data)
                with db_lock:
                    item_id = db.add_item("screenshot", image_bytes, timestamp_str)

                # Generate thumbnail asynchronously
                process_thumbnail_async(item_id, image_bytes)

                # Optionally save to disk
                if SCREENSHOT_SAVE_DIR:
                    filename = f"screenshot_{timestamp.strftime('%Y%m%d_%H%M%S')}.png"
                    filepath = Path(SCREENSHOT_SAVE_DIR) / filename

                    # Decode base64 and save
                    with open(filepath, "wb") as f:
                        f.write(base64.b64decode(image_data))

                    logging.info(f"📸 Screenshot captured and saved: {filename}")
                else:
                    logging.info(f"📸 Screenshot captured ({len(image_data)} bytes)")

                logging.info(f"  (History: {len(history)} items)\n")

        except Exception as e:
            logging.error(f"⚠ Screenshot worker error: {e}")


def prepare_item_for_ui(item: dict) -> dict:
    """Convert database item to UI-renderable format"""
    item_type = item["type"]
    data = item["data"]
    thumbnail = item.get("thumbnail")

    if item_type == "text" or item_type == "url":
        content = data.decode("utf-8") if isinstance(data, bytes) else data
        thumbnail_b64 = None
    elif item_type == "file":
        # Extract file metadata from combined data
        try:
            separator = b'\n---FILE_CONTENT---\n'
            if separator in data:
                metadata_bytes, _ = data.split(separator, 1)
                metadata_json = metadata_bytes.decode('utf-8')
                metadata = json.loads(metadata_json)
                content = metadata  # Send metadata as content
            else:
                content = {"error": "Invalid file data format"}
            thumbnail_b64 = None
        except Exception as e:
            logging.error(f"Error parsing file metadata for item {item['id']}: {e}")
            content = {"error": "Failed to parse file metadata"}
            thumbnail_b64 = None
    elif item_type.startswith("image/") or item_type == "screenshot":
        # DON'T send full image in WebSocket messages - too large!
        # Only send item ID and thumbnail
        content = None  # Client will request full image only when saving
        # Use thumbnail if available, generate one if not
        if thumbnail:
            thumbnail_b64 = base64.b64encode(thumbnail).decode("utf-8")
            # Defensive check: if thumbnail is still too large, don't send it
            if len(thumbnail_b64) > 500 * 1024: # 500KB limit for base64 thumbnail
                logging.warning(f"Thumbnail for item {item['id']} is too large ({len(thumbnail_b64)} bytes), sending None.")
                thumbnail_b64 = None
        else:
            # No thumbnail yet - generate a placeholder or small version
            try:
                # Try to generate thumbnail on-the-fly for old items
                thumb = generate_thumbnail(data, max_size=250)
                if thumb:
                    thumbnail_b64 = base64.b64encode(thumb).decode("utf-8")
                    if len(thumbnail_b64) > 500 * 1024: # 500KB limit for base64 thumbnail
                        logging.warning(f"Generated thumbnail for item {item['id']} is too large ({len(thumbnail_b64)} bytes), sending None.")
                        thumbnail_b64 = None
                    else:
                        # Update database with generated thumbnail
                        with db_lock:
                            db.update_thumbnail(item["id"], thumb)
                else:
                    thumbnail_b64 = None
            except BaseException:
                thumbnail_b64 = None
    else:
        # For any other non-text type, ensure content is None to prevent large binary data
        content = None
        thumbnail_b64 = None

    logging.debug(f"Item {item['id']} ({item_type}): content_size={len(content) if content else 0}, thumbnail_size={len(thumbnail_b64) if thumbnail_b64 else 0}")

    return {
        "id": item["id"],
        "type": item_type,
        "content": content,  # None for images
        "thumbnail": thumbnail_b64,
        "timestamp": item["timestamp"],
        "name": item.get("name"),  # Include name field
    }


async def websocket_handler(websocket):
    """Handle WebSocket client connections from UI"""
    global ws_clients, last_known_id

    logging.info(f"WebSocket client connected from {websocket.remote_address}")
    ws_clients.add(websocket)

    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                action = data.get("action")

                if action == "get_history":
                    limit = data.get("limit", settings.max_page_length)
                    offset = data.get("offset", 0)
                    sort_order = data.get("sort_order", "DESC")
                    filters = data.get("filters", None)

                    logging.info(f"[FILTER] get_history request with filters: {filters}")

                    # Use lock for thread-safe database access
                    with db_lock:
                        items = db.get_items(limit=limit, offset=offset, sort_order=sort_order, filters=filters)
                        total_count = db.get_total_count()
                        logging.info(f"[FILTER] Returned {len(items)} items (total: {total_count})")

                    # Convert to UI format
                    ui_items = [prepare_item_for_ui(item) for item in items]

                    response = {"type": "history", "items": ui_items, "total_count": total_count, "offset": offset}
                    await websocket.send(json.dumps(response))

                elif action == "get_full_image":
                    # Get full image data for saving
                    item_id = data.get("id")
                    if item_id:
                        with db_lock:
                            item = db.get_item(item_id)
                        if item and (item["type"].startswith("image/") or item["type"] == "screenshot"):
                            full_image_b64 = base64.b64encode(item["data"]).decode("utf-8")
                            response = {"type": "full_image", "id": item_id, "content": full_image_b64}
                            await websocket.send(json.dumps(response))
                        elif item and item["type"] == "file":
                            # For files, send the full file data
                            separator = b'\n---FILE_CONTENT---\n'
                            if separator in item["data"]:
                                _, file_content = item["data"].split(separator, 1)
                                file_content_b64 = base64.b64encode(file_content).decode("utf-8")
                                response = {"type": "full_file", "id": item_id, "content": file_content_b64}
                                await websocket.send(json.dumps(response))
                            else:
                                response = {"type": "error", "message": "Invalid file data format"}
                                await websocket.send(json.dumps(response))

                elif action == "delete_item":
                    item_id = data.get("id")
                    if item_id:
                        with db_lock:
                            db.delete_item(item_id)
                        # Notify all clients
                        await broadcast_ws({"type": "item_deleted", "id": item_id})

                elif action == "get_recently_pasted":
                    limit = data.get("limit", settings.max_page_length)
                    offset = data.get("offset", 0)
                    sort_order = data.get("sort_order", "DESC")

                    # Get recently pasted items with JOIN
                    with db_lock:
                        items = db.get_recently_pasted(limit=limit, offset=offset, sort_order=sort_order)
                        total_count = db.get_pasted_count()

                    # Convert to UI format
                    ui_items = [prepare_item_for_ui(item) for item in items]

                    # Add pasted_timestamp to each item
                    for i, item in enumerate(items):
                        ui_items[i]["pasted_timestamp"] = item["pasted_timestamp"]

                    response = {"type": "recently_pasted", "items": ui_items, "total_count": total_count, "offset": offset}
                    await websocket.send(json.dumps(response))

                elif action == "record_paste":
                    item_id = data.get("id")
                    if item_id:
                        logging.info(f"Received record_paste request for item {item_id}")
                        with db_lock:
                            paste_id = db.add_pasted_item(item_id)
                        logging.info(f"Recorded paste for item {item_id} (paste_id={paste_id})")

                elif action == "search":
                    query = data.get("query", "").strip()
                    limit = data.get("limit", 100)
                    filters = data.get("filters", [])

                    if query:
                        logging.info(f"Searching for: '{query}' (limit={limit}, filters={filters})")
                        with db_lock:
                            results = db.search_items(query, limit, filters)

                        # Prepare items for UI (same as get_page)
                        ui_items = []
                        for item in results:
                            ui_item = prepare_item_for_ui(item)
                            ui_items.append(ui_item)

                        response = {
                            "type": "search_results",
                            "query": query,
                            "items": ui_items,
                            "count": len(ui_items)
                        }
                        await websocket.send(json.dumps(response))
                        logging.info(f"Search complete: {len(ui_items)} results")
                    else:
                        # Empty query returns empty results
                        response = {"type": "search_results", "query": "", "items": [], "count": 0}
                        await websocket.send(json.dumps(response))

                # ========== Tag Management Handlers ==========
                elif action == "get_tags":
                    logging.info("Fetching all tags")
                    with db_lock:
                        tags = db.get_all_tags()
                    response = {"type": "tags", "tags": tags}
                    await websocket.send(json.dumps(response))
                    logging.info(f"Sent {len(tags)} tags")

                elif action == "create_tag":
                    name = data.get("name")
                    description = data.get("description")
                    color = data.get("color")

                    if name:
                        logging.info(f"Creating tag: '{name}'")
                        try:
                            with db_lock:
                                tag_id = db.create_tag(name, description, color)
                                tag = db.get_tag(tag_id)
                            response = {"type": "tag_created", "tag": tag, "success": True}
                            await websocket.send(json.dumps(response))
                            logging.info(f"Created tag: ID={tag_id}, Name='{name}'")
                        except Exception as e:
                            response = {"type": "tag_created", "success": False, "error": str(e)}
                            await websocket.send(json.dumps(response))
                            logging.error(f"Failed to create tag: {e}")
                    else:
                        response = {"type": "tag_created", "success": False, "error": "Name is required"}
                        await websocket.send(json.dumps(response))

                elif action == "update_tag":
                    tag_id = data.get("tag_id")
                    name = data.get("name")
                    description = data.get("description")
                    color = data.get("color")

                    if tag_id:
                        logging.info(f"Updating tag ID={tag_id}")
                        with db_lock:
                            success = db.update_tag(tag_id, name, description, color)
                            if success:
                                tag = db.get_tag(tag_id)
                        response = {"type": "tag_updated", "tag": tag if success else None, "success": success}
                        await websocket.send(json.dumps(response))
                        logging.info(f"Updated tag ID={tag_id}: {success}")
                    else:
                        response = {"type": "tag_updated", "success": False, "error": "tag_id is required"}
                        await websocket.send(json.dumps(response))

                elif action == "delete_tag":
                    tag_id = data.get("tag_id")

                    if tag_id:
                        logging.info(f"Deleting tag ID={tag_id}")
                        with db_lock:
                            success = db.delete_tag(tag_id)
                        response = {"type": "tag_deleted", "tag_id": tag_id, "success": success}
                        await websocket.send(json.dumps(response))
                        logging.info(f"Deleted tag ID={tag_id}: {success}")
                    else:
                        response = {"type": "tag_deleted", "success": False, "error": "tag_id is required"}
                        await websocket.send(json.dumps(response))

                elif action == "add_item_tag":
                    item_id = data.get("item_id")
                    tag_id = data.get("tag_id")

                    if item_id and tag_id:
                        logging.info(f"Adding tag {tag_id} to item {item_id}")
                        with db_lock:
                            success = db.add_tag_to_item(item_id, tag_id)
                        response = {"type": "item_tag_added", "item_id": item_id, "tag_id": tag_id, "success": success}
                        await websocket.send(json.dumps(response))
                        logging.info(f"Added tag {tag_id} to item {item_id}: {success}")
                    else:
                        response = {"type": "item_tag_added", "success": False, "error": "item_id and tag_id are required"}
                        await websocket.send(json.dumps(response))

                elif action == "remove_item_tag":
                    item_id = data.get("item_id")
                    tag_id = data.get("tag_id")

                    if item_id and tag_id:
                        logging.info(f"Removing tag {tag_id} from item {item_id}")
                        with db_lock:
                            success = db.remove_tag_from_item(item_id, tag_id)
                        response = {"type": "item_tag_removed", "item_id": item_id, "tag_id": tag_id, "success": success}
                        await websocket.send(json.dumps(response))
                        logging.info(f"Removed tag {tag_id} from item {item_id}: {success}")
                    else:
                        response = {"type": "item_tag_removed", "success": False, "error": "item_id and tag_id are required"}
                        await websocket.send(json.dumps(response))

                elif action == "get_item_tags":
                    item_id = data.get("item_id")

                    if item_id:
                        logging.info(f"Fetching tags for item {item_id}")
                        with db_lock:
                            tags = db.get_tags_for_item(item_id)
                        response = {"type": "item_tags", "item_id": item_id, "tags": tags}
                        await websocket.send(json.dumps(response))
                        logging.info(f"Sent {len(tags)} tags for item {item_id}")
                    else:
                        response = {"type": "item_tags", "tags": [], "error": "item_id is required"}
                        await websocket.send(json.dumps(response))

                elif action == "get_items_by_tags":
                    tag_ids = data.get("tag_ids", [])
                    match_all = data.get("match_all", False)
                    limit = data.get("limit", 100)
                    offset = data.get("offset", 0)

                    if tag_ids:
                        logging.info(f"Fetching items by tags: {tag_ids} (match_all={match_all})")
                        with db_lock:
                            results = db.get_items_by_tags(tag_ids, match_all, limit, offset)

                        # Prepare items for UI
                        ui_items = []
                        for item in results:
                            ui_item = prepare_item_for_ui(item)
                            ui_items.append(ui_item)

                        response = {"type": "items_by_tags", "items": ui_items, "count": len(ui_items)}
                        await websocket.send(json.dumps(response))
                        logging.info(f"Sent {len(ui_items)} items for tags {tag_ids}")
                    else:
                        response = {"type": "items_by_tags", "items": [], "count": 0}
                        await websocket.send(json.dumps(response))

                elif action == "update_item_name":
                    item_id = data.get("item_id")
                    name = data.get("name")

                    if item_id is not None:
                        logging.info(f"Updating name for item {item_id}: '{name}'")
                        with db_lock:
                            success = db.update_item_name(item_id, name)
                        response = {"type": "item_name_updated", "item_id": item_id, "name": name, "success": success}
                        await websocket.send(json.dumps(response))

                        # Broadcast to all clients that item was updated
                        if success:
                            await broadcast_ws({"type": "item_updated", "item_id": item_id, "name": name})
                        logging.info(f"Updated name for item {item_id}: {success}")
                    else:
                        response = {"type": "item_name_updated", "success": False, "error": "item_id is required"}
                        await websocket.send(json.dumps(response))

                elif action == "get_file_extensions":
                    logging.info("Fetching file extensions")
                    with db_lock:
                        extensions = db.get_file_extensions()
                    response = {"type": "file_extensions", "extensions": extensions}
                    await websocket.send(json.dumps(response))
                    logging.info(f"Sent {len(extensions)} file extensions")

            except Exception as e:
                logging.error(f"Error handling WebSocket message: {e}")

                traceback.print_exc()

    except websockets.exceptions.ConnectionClosed:
        pass
    except Exception as e:
        logging.error(f"WebSocket handler error: {e}")

        traceback.print_exc()
    finally:
        ws_clients.remove(websocket)
        logging.info(f"WebSocket client disconnected")


async def broadcast_ws(message: dict):
    """Broadcast message to all WebSocket clients"""
    if ws_clients:
        message_json = json.dumps(message)
        await asyncio.gather(*[client.send(message_json) for client in ws_clients], return_exceptions=True)


def watch_for_new_items(loop):
    """Background thread to watch for new database items and broadcast to WebSocket clients"""
    global last_known_id

    logging.info("Starting database watcher for WebSocket broadcasts...")

    while True:
        try:
            with db_lock:
                latest_id = db.get_latest_id()

            if latest_id and latest_id > last_known_id:
                # New items detected
                logging.info(f"📢 Broadcasting new items {last_known_id + 1} to {latest_id}")
                for item_id in range(last_known_id + 1, latest_id + 1):
                    with db_lock:
                        item = db.get_item(item_id)
                    if item:
                        ui_item = prepare_item_for_ui(item)

                        # Broadcast to all clients
                        message = {"type": "new_item", "item": ui_item}

                        # Schedule broadcast in async loop
                        asyncio.run_coroutine_threadsafe(broadcast_ws(message), loop)
                        logging.info(f"  → Broadcast item {item_id} ({item['type']}) to {len(ws_clients)} clients")

                last_known_id = latest_id

        except Exception as e:
            logging.error(f"Error in database watcher: {e}")

        time.sleep(0.5)


async def start_websocket_server():
    """Start WebSocket server for UI"""
    logging.info("Starting WebSocket server on ws://localhost:8765")
    configured_max_size = 5 * 1024 * 1024 # 5MB
    logging.info(f"WebSocket server configured with max_size: {configured_max_size} bytes")
    async with websockets.serve(websocket_handler, "localhost", 8765, max_size=configured_max_size):
        await asyncio.Future()  # Run forever


def start_server():
    """Start UNIX socket server to receive clipboard data"""
    socket_path = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "simple-clipboard.sock")

    # Remove existing socket if it exists
    try:
        os.unlink(socket_path)
    except FileNotFoundError:
        pass

    # Create UNIX socket
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(socket_path)
    server.listen(5)

    logging.info(f"Listening on {socket_path}")
    logging.info("Waiting for clipboard events from GNOME Shell extension...\n")

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
    logging.info("WebSocket server started\n")

    try:
        while True:
            conn, _ = server.accept()
            try:
                # Read data until we get a newline (for JSON messages)
                full_data = b""
                while b"\n" not in full_data:
                    data = conn.recv(4096)
                    if not data:
                        break
                    full_data += data

                if full_data:
                    message = json.loads(full_data.decode("utf-8").strip())

                    # Handle UI requests
                    if "action" in message:
                        if message["action"] == "get_history":
                            try:
                                response = json.dumps({"history": history}) + "\n"
                                conn.sendall(response.encode("utf-8"))
                            except BrokenPipeError:
                                pass  # Client disconnected
                        # Don't close connection yet - let client close it
                        continue

                    # Handle clipboard events from extension
                    if message["type"] == "text":
                        text = message["content"]
                        text_bytes = text.encode("utf-8")

                        # Check for URL
                        url_pattern = re.compile(r'https?://\S+')
                        is_url = url_pattern.search(text) is not None
                        item_type = "url" if is_url else "text"

                        # Calculate hash for deduplication
                        from database import ClipboardDB

                        text_hash = ClipboardDB.calculate_hash(text_bytes)

                        # Check if hash already exists in database
                        timestamp = datetime.now().isoformat()

                        with db_lock:
                            existing_item_id = db.get_item_by_hash(text_hash)

                        if existing_item_id:
                            # Duplicate found - update timestamp to move to top
                            logging.info(f"↻ Updating duplicate {item_type} ({len(text)} characters) - moving to top\n")
                            with db_lock:
                                db.update_timestamp(existing_item_id, timestamp)
                                # Get the updated item to broadcast
                                item = db.get_item(existing_item_id)
                        else:
                            # New item - add to database
                            history.append(
                                {
                                    "type": item_type,
                                    "content": text,
                                    "timestamp": timestamp,
                                }
                            )

                            # Save to database with hash (thread-safe)
                            with db_lock:
                                item_id = db.add_item(item_type, text_bytes, timestamp, data_hash=text_hash)
                                item = db.get_item(item_id)

                            # Log clipboard event (no content for privacy)
                            logging.info(f"✓ Copied {item_type} ({len(text)} characters)")
                            logging.info(f"  (History: {len(history)} items)\n")

                    elif message["type"].startswith("image/"):
                        # Handle image data (base64 encoded)
                        image_content = json.loads(message["content"])
                        image_data = image_content["data"]
                        image_bytes = base64.b64decode(image_data)

                        # Calculate hash for deduplication
                        from database import ClipboardDB

                        image_hash = ClipboardDB.calculate_hash(image_bytes)

                        # Check if hash already exists in database
                        timestamp = datetime.now().isoformat()

                        with db_lock:
                            existing_item_id = db.get_item_by_hash(image_hash)

                        if existing_item_id:
                            # Duplicate found - update timestamp to move to top
                            logging.info(
                                f"↻ Updating duplicate image ({message['type']}, {len(image_bytes)} bytes) - moving to top\n"
                            )
                            with db_lock:
                                db.update_timestamp(existing_item_id, timestamp)
                        else:
                            # New item - add to database
                            timestamp = datetime.now().isoformat()

                            history.append(
                                {
                                    "type": message["type"],
                                    "content": image_data,
                                    "timestamp": timestamp,
                                }
                            )

                            # Save to database with hash (thread-safe)
                            with db_lock:
                                item_id = db.add_item(message["type"], image_bytes, timestamp, data_hash=image_hash)

                            # Generate thumbnail asynchronously
                            process_thumbnail_async(item_id, image_bytes)

                            logging.info(
                                f"✓ Copied image ({message['type']}, {len(image_bytes)} bytes)"
                            )
                            logging.info(f"  (History: {len(history)} items)\n")

                    elif message["type"] == "file":
                        # Handle file data
                        file_uri = message["content"]
                        logging.info(f"Received file URI: {file_uri}")

                        # Process the file
                        file_data = process_file(file_uri)

                        if file_data:
                            metadata = file_data['metadata']
                            file_content = file_data['content']

                            # Calculate hash for deduplication
                            from database import ClipboardDB

                            # For directories, hash the path instead of empty content
                            if metadata.get('is_directory'):
                                hash_input = metadata['original_path'].encode('utf-8')
                            else:
                                hash_input = file_content

                            file_hash = ClipboardDB.calculate_hash(hash_input)

                            # Check if hash already exists in database
                            timestamp = datetime.now().isoformat()

                            with db_lock:
                                existing_item_id = db.get_item_by_hash(file_hash)

                            if existing_item_id:
                                # Duplicate found - update timestamp to move to top
                                logging.info(
                                    f"↻ Updating duplicate file ({metadata['name']}, {metadata['size']} bytes) - moving to top\n"
                                )
                                with db_lock:
                                    db.update_timestamp(existing_item_id, timestamp)
                            else:
                                # New item - add to database
                                # Store metadata as JSON in the data field along with content
                                # We'll store: metadata JSON + separator + file content
                                metadata_json = json.dumps(metadata)
                                metadata_bytes = metadata_json.encode('utf-8')
                                separator = b'\n---FILE_CONTENT---\n'
                                combined_data = metadata_bytes + separator + file_content

                                # Add to history (in-memory)
                                history.append(
                                    {
                                        "type": "file",
                                        "content": metadata,  # Store metadata in history
                                        "timestamp": timestamp,
                                    }
                                )

                                # Save to database with hash (thread-safe)
                                with db_lock:
                                    item_id = db.add_item("file", combined_data, timestamp, data_hash=file_hash)

                                logging.info(
                                    f"✓ Copied file: {metadata['name']} ({metadata['size']} bytes, {metadata['mime_type']})"
                                )
                                logging.info(f"  (History: {len(history)} items)\n")
                        else:
                            logging.warning("Failed to process file URI")

            except json.JSONDecodeError:
                logging.warning("Received malformed JSON message on UNIX socket.")
            except Exception as e:
                logging.error(f"Error handling client connection: {e}")
            finally:
                conn.close()

    except KeyboardInterrupt:
        logging.info("\nStopping server...")
        logging.info(f"Total items saved: {len(history)}")
    finally:
        server.close()
        try:
            os.unlink(socket_path)
        except OSError as e:
            logging.error(f"Error unlinking socket: {e}")


if __name__ == "__main__":
    start_server()
