# TFCBM UI - GTK4 Clipboard Manager Interface

A modern GTK4/Libadwaita interface for the TFCBM clipboard manager.

## Features

- Clean, minimal design using Libadwaita components
- Displays clipboard history (text and images)
- Window positioned on the left side of the screen (~350px wide)
- Real-time updates from the clipboard server
- System font integration
- Settings button (placeholder for future functionality)

## Architecture

The UI connects to the TFCBM server via UNIX socket to:
1. Request clipboard history on startup
2. Receive new clipboard items in real-time

### Communication Protocol

The UI sends JSON requests to the server socket:
```json
{"action": "get_history"}
```

The server responds with:
```json
{
  "history": [
    {
      "type": "text",
      "content": "clipboard content",
      "timestamp": "2025-11-14T10:15:30.123456"
    },
    {
      "type": "image/png",
      "content": "<base64 encoded image>",
      "timestamp": "2025-11-14T10:16:45.789012"
    }
  ]
}
```

## Running

The UI is automatically started by the `load.sh` script, which:
1. Kills any existing UI instances
2. Starts the server in the background
3. Launches the UI in the foreground

You can also run it manually:
```bash
source .venv/bin/activate
python3 ui/main.py
```

## Requirements

- Python 3.10+
- GTK4
- Libadwaita
- PyGObject

System packages (Fedora):
```bash
sudo dnf install gtk4 libadwaita python3-gobject
```

Python packages:
```bash
pip install PyGObject
```

## File Structure

- `main.py` - Main application entry point
  - `ClipboardApp` - Adw.Application subclass
  - `ClipboardWindow` - Main application window
  - `ClipboardItemRow` - Custom row widget for displaying clipboard items

## Future Enhancements

- [ ] Settings dialog
- [ ] Search/filter functionality
- [ ] Item deletion
- [ ] Copy item back to clipboard on click
- [ ] Keyboard shortcuts
- [ ] Auto-refresh/polling for new items
- [ ] Export history
