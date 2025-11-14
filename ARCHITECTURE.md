# TFCBM Architecture

## Overview

TFCBM (The F*cking Clipboard Manager) is a clipboard history manager for GNOME Wayland with a GTK4 UI.

## Architecture Components

```
┌─────────────────────┐
│  GNOME Extension    │
│  (JavaScript)       │
└──────────┬──────────┘
           │ Clipboard events
           ▼
   ┌───────────────────┐
   │  UNIX Socket      │
   └─────────┬─────────┘
             │
             ▼
┌────────────────────────────────┐
│   tfcbm_server.py              │
│                                │
│  ┌──────────────────────────┐ │
│  │  UNIX Socket Handler     │ │
│  │  (receives from ext)     │ │
│  └───────────┬──────────────┘ │
│              │                 │
│              ▼                 │
│  ┌──────────────────────────┐ │
│  │  SQLite Database         │ │
│  │  - id, timestamp         │ │
│  │  - type, data (BLOB)     │ │
│  └───────────┬──────────────┘ │
│              │                 │
│              ▼                 │
│  ┌──────────────────────────┐ │
│  │  Database Watcher        │ │
│  │  (thread)                │ │
│  └───────────┬──────────────┘ │
│              │                 │
│              ▼                 │
│  ┌──────────────────────────┐ │
│  │  WebSocket Server        │ │
│  │  ws://localhost:8765     │ │
│  └───────────┬──────────────┘ │
└──────────────┼────────────────┘
               │
               │ WebSocket messages
               ▼
      ┌────────────────┐
      │  UI (GTK4)     │
      │  - History     │
      │  - Copy        │
      │  - Save        │
      └────────────────┘
```

## Data Flow

### 1. Clipboard Event Flow
1. User copies text/image in GNOME
2. GNOME Extension detects clipboard change
3. Extension sends event via UNIX socket to `tfcbm_server.py`
4. Server saves to SQLite database (thread-safe)
5. Server prints to console
6. Database watcher detects new item
7. WebSocket server broadcasts to all connected UIs

### 2. UI Connection Flow
1. UI connects to WebSocket server
2. UI requests history: `{"action": "get_history", "limit": 100}`
3. Server queries database and sends items
4. UI displays items in GTK ListBox
5. UI listens for real-time `new_item` broadcasts

## Database Schema

```sql
CREATE TABLE clipboard_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,           -- ISO format
    type TEXT NOT NULL,                -- text, image/png, screenshot
    data BLOB NOT NULL,                -- text bytes or image bytes
    thumbnail BLOB,                    -- 250x250 thumbnail (PNG, for images only)
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_timestamp ON clipboard_items(timestamp DESC);
```

## Thumbnail Generation

Images are automatically thumbnailed using **Pillow** (PIL):
- **Max size**: 250x250 pixels (maintains aspect ratio)
- **Format**: PNG (optimized)
- **Processing**: Asynchronous (ThreadPoolExecutor with 2 workers)
- **Conversion**: RGBA/P modes converted to RGB for compatibility

### Flow:
1. Image saved to database (data column)
2. Thumbnail generation submitted to thread pool
3. Thumbnail generated using Pillow
4. Database updated with thumbnail (thumbnail column)
5. WebSocket broadcasts include thumbnail for UI display

## Data Conversion

### Storage
- **Text**: Stored as UTF-8 encoded bytes
- **Images**: Stored as raw image bytes (PNG, JPEG, etc.)

### UI Format
The server converts database items to UI-renderable format:
- **Text**: Bytes → UTF-8 string
- **Images**:
  - `content`: Full image bytes → Base64 string
  - `thumbnail`: Thumbnail bytes → Base64 string (or falls back to content if not yet generated)

The UI displays thumbnails for better performance and cleaner layout.

## WebSocket Protocol

### Client → Server

**Get History:**
```json
{
  "action": "get_history",
  "limit": 100
}
```

**Delete Item:**
```json
{
  "action": "delete_item",
  "id": 123
}
```

### Server → Client

**History Response:**
```json
{
  "type": "history",
  "items": [
    {
      "id": 1,
      "type": "text",
      "content": "clipboard text",
      "thumbnail": null,
      "timestamp": "2025-11-14T10:15:30.123456"
    },
    {
      "id": 2,
      "type": "image/png",
      "content": "base64fullimage...",
      "thumbnail": "base64thumbnail...",
      "timestamp": "2025-11-14T10:16:45.789012"
    }
  ]
}
```

**New Item Broadcast:**
```json
{
  "type": "new_item",
  "item": {
    "id": 2,
    "type": "image/png",
    "content": "base64encodedimage...",
    "timestamp": "2025-11-14T10:16:45.789012"
  }
}
```

**Item Deleted:**
```json
{
  "type": "item_deleted",
  "id": 123
}
```

## UI Features

### Per-Item Actions
- **Copy Button**: Copies item back to system clipboard
  - Text: Uses `Gdk.Clipboard.set()`
  - Images: Converts base64 → texture → clipboard
- **Save Button**: Opens file save dialog
  - Text: Saves as .txt file
  - Images: Saves as image file (.png, .jpg, etc.)

### Window Properties
- Width: 350px
- Position: Left side of screen
- Style: Libadwaita (adaptive, modern)
- Header: Settings and close buttons only

## Thread Safety

All database operations use `db_lock` (threading.Lock()) to ensure thread-safe access:
- UNIX socket handler (main thread)
- WebSocket handlers (async thread pool)
- Database watcher (background thread)

## File Locations

- **Database**: `~/.local/share/tfcbm/clipboard.db`
- **Server logs**: `./tfcbm_server.log`
- **UNIX Socket**: `/run/user/1000/simple-clipboard.sock`
- **WebSocket**: `ws://localhost:8765`

## Running the System

```bash
./load.sh
```

This will:
1. Install GNOME extension
2. Install Python dependencies
3. Start tfcbm_server.py (UNIX socket + WebSocket + Database)
4. Launch GTK4 UI
5. Display server logs in terminal
6. Support clean Ctrl+C exit
