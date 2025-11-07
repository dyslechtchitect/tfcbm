# Screenshot Recording Feature

## Overview

TFCBM now includes automatic screenshot recording that captures your screen at regular intervals and adds screenshots to the clipboard history.

## Installation

### Install grim (Wayland screenshot tool)

```bash
sudo dnf install grim
```

## Configuration

Edit `tfcbm_server.py` to configure screenshot behavior:

```python
# Screenshot configuration (lines 18-21)
SCREENSHOT_INTERVAL = 30  # seconds between screenshots (default: 30)
SCREENSHOT_ENABLED = True  # Set to False to disable automatic screenshots
SCREENSHOT_SAVE_DIR = None  # Set to './screenshots' to save screenshots to disk
```

### Examples:

**Disable screenshots:**
```python
SCREENSHOT_ENABLED = False
```

**Capture every 60 seconds:**
```python
SCREENSHOT_INTERVAL = 60
```

**Save screenshots to disk:**
```python
SCREENSHOT_SAVE_DIR = './screenshots'  # Creates screenshots/ directory
```

## Usage

### Start the server with screenshot capture:

```bash
python3 tfcbm_server.py
```

You'll see:
```
Listening on /run/user/1000/simple-clipboard.sock
Waiting for clipboard events from GNOME Shell extension...

📸 Screenshot capture started (interval: 30s)
```

### Test screenshot functionality:

```bash
python3 test_screenshot.py
```

Expected output:
```
✓ Screenshot captured successfully!
  File: /tmp/test_screenshot_1234567890.png
  Size: 1,234,567 bytes
  Base64 size: 1,646,756 characters
✓ Cleanup successful

✓ Screenshot saved: test_screenshots/screenshot_20251107_123456.png
  Size: 1,234,567 bytes

✓ All tests passed! Screenshot functionality is working.
```

## How It Works

1. **Background Thread**: When `tfcbm_server.py` starts, it launches a background thread that captures screenshots at regular intervals.

2. **Capture**: Uses `grim` (Wayland-native screenshot tool) to capture full-screen screenshots.

3. **Storage**: Screenshots are:
   - Added to clipboard history (always)
   - Optionally saved to disk as PNG files with timestamps
   - Base64 encoded for storage in memory

4. **History**: Screenshots are added to the same `history` list as clipboard text and images, with type `'screenshot'`.

## Screenshot Data Structure

```python
{
    'type': 'screenshot',
    'content': '<base64-encoded-png-data>',
    'timestamp': '2025-11-07T12:34:56.789012'
}
```

## Troubleshooting

### Error: "grim: command not found"

Install grim:
```bash
sudo dnf install grim
```

### Screenshots not appearing in history

1. Check that `SCREENSHOT_ENABLED = True` in `tfcbm_server.py`
2. Verify grim is installed: `which grim`
3. Check server output for error messages

### High memory usage

Screenshots are stored as base64-encoded PNG data in memory. To reduce memory usage:

1. Increase `SCREENSHOT_INTERVAL` (capture less frequently)
2. Save screenshots to disk and clear history periodically
3. Implement history size limits (future feature)

## File Locations

- **Server code**: `tfcbm_server.py`
- **Test script**: `test_screenshot.py`
- **Screenshot save directory**: Configurable via `SCREENSHOT_SAVE_DIR`
- **Temporary files**: `/tmp/tfcbm_screenshot_*.png` (auto-cleaned)

## Future Enhancements

- [ ] History size limits (max items or max memory)
- [ ] Export history to JSON
- [ ] GUI for viewing screenshots
- [ ] Screenshot search by timestamp
- [ ] Configurable screenshot quality/compression
- [ ] Area/window selection (not just full screen)
