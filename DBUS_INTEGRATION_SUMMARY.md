# TFCBM DBus Integration - Summary of Changes

This document summarizes all changes made to integrate TFCBM with the decoupled GNOME Shell extension.

## Overview

The TFCBM application has been updated to work with the GNOME-compliant extension via DBus communication. The extension no longer launches or manages the TFCBM process - instead, both run independently and communicate via DBus.

## Files Created

### 1. `dbus_service.py` (New)
**Location:** `/home/ron/Documents/git/TFCBM/dbus_service.py`

A reusable DBus service module that implements the `org.tfcbm.ClipboardManager` DBus interface.

**Features:**
- Implements all DBus methods: `Activate`, `ShowSettings`, `Quit`, `OnClipboardChange`
- Can be used by both UI and server
- Handles window activation, settings navigation, and clipboard events
- Graceful error handling

### 2. `org.tfcbm.ClipboardManager.desktop.autostart` (New)
**Location:** `/home/ron/Documents/git/TFCBM/org.tfcbm.ClipboardManager.desktop.autostart`

Autostart configuration file for TFCBM.

**Usage:**
```bash
cp org.tfcbm.ClipboardManager.desktop.autostart \
   ~/.config/autostart/org.tfcbm.ClipboardManager.desktop
```

**Note:** Update paths in the file to match your installation directory.

### 3. `GNOME_EXTENSION_INTEGRATION.md` (New)
**Location:** `/home/ron/Documents/git/TFCBM/GNOME_EXTENSION_INTEGRATION.md`

Comprehensive guide for setting up and using the DBus integration.

**Contents:**
- Installation steps
- DBus interface documentation
- Testing procedures
- Troubleshooting guide

### 4. `DBUS_INTEGRATION_SUMMARY.md` (New - This File)
Summary of all changes made for DBus integration.

## Files Modified

### 1. `tfcbm_server.py`

**Changes Made:**

#### Added Imports:
```python
import gi
gi.require_version('GLib', '2.0')
from gi.repository import GLib
from dbus_service import TFCBMDBusService
```

#### Added Function: `handle_clipboard_event_dbus(event_data: dict)`
**Line:** ~882-1020

Processes clipboard events received from the GNOME extension via DBus.

**Features:**
- Handles text, image, and file clipboard types
- Deduplication using hash checking
- Formatted text support (HTML/RTF)
- URL detection
- Thread-safe database access
- Identical logic to Unix socket handler for consistency

#### Added DBus Service Thread in `start_server()`
**Line:** ~1065-1092

Starts the DBus service in a separate thread with its own GLib main loop.

**Implementation:**
```python
def run_dbus_service():
    """Run DBus service with GLib main loop"""
    class DBusApp:
        def get_dbus_connection(self):
            from gi.repository import Gio
            return Gio.bus_get_sync(Gio.BusType.SESSION, None)

    dbus_app = DBusApp()
    dbus_service = TFCBMDBusService(dbus_app, clipboard_handler=handle_clipboard_event_dbus)

    if dbus_service.start():
        logging.info("✓ DBus service started for GNOME extension integration")
        loop = GLib.MainLoop()
        loop.run()

dbus_thread = threading.Thread(target=run_dbus_service, daemon=True)
dbus_thread.start()
```

**Note:** Unix socket server remains functional for backward compatibility.

### 2. `ui/application/clipboard_app.py`

**Changes Made:**

#### Added Imports:
```python
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from dbus_service import TFCBMDBusService
```

#### Modified `__init__()`:
Added `self.dbus_service = None` to store DBus service instance.

#### Replaced `_setup_dbus()` with New Implementation:
**Before:** Manual DBus registration with inline XML
**After:** Uses `TFCBMDBusService` module

```python
# In do_startup()
self.dbus_service = TFCBMDBusService(self)
self.dbus_service.start()
```

#### Removed Functions:
- `_setup_dbus()` - Replaced by `TFCBMDBusService`
- `_handle_dbus_method_call()` - Moved to `TFCBMDBusService`

**Result:** Cleaner code, better separation of concerns.

## DBus Interface Specification

### Service Information
- **Bus Name:** `org.tfcbm.ClipboardManager`
- **Object Path:** `/org/tfcbm/ClipboardManager`
- **Interface:** `org.tfcbm.ClipboardManager`

### Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `Activate` | `u → void` | Toggle window visibility (u = timestamp) |
| `ShowSettings` | `u → void` | Show settings page (u = timestamp) |
| `Quit` | `void → void` | Quit the application |
| `OnClipboardChange` | `s → void` | Receive clipboard event (s = JSON string) |

### Event Format for `OnClipboardChange`

```json
{
  "type": "text|image/png|image/jpeg|file",
  "data": "content or base64 encoded data",
  "formattedContent": "optional base64 HTML/RTF content",
  "formatType": "html|rtf"
}
```

## Architecture Diagram

```
┌────────────────────────────────────────────────────────────┐
│                    GNOME Shell Extension                    │
│                (tfcbm-clipboard-monitor@github.com)         │
├────────────────────────────────────────────────────────────┤
│ • Monitors clipboard (St.Clipboard)                        │
│ • Manages tray icon & keyboard shortcuts                   │
│ • Sends clipboard events via DBus                          │
│   OnClipboardChange(eventData)                             │
└────────────────────────────┬───────────────────────────────┘
                             │
                             │ DBus Session Bus
                             │ org.tfcbm.ClipboardManager
                             │
┌────────────────────────────┴───────────────────────────────┐
│                      TFCBM Application                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  tfcbm_server.py (Backend)                          │  │
│  ├─────────────────────────────────────────────────────┤  │
│  │ • Registers DBus service (thread + GLib loop)       │  │
│  │ • Receives clipboard events from extension          │  │
│  │ • Processes & stores clipboard data in database     │  │
│  │ • WebSocket server for UI communication             │  │
│  │ • Unix socket (legacy, still functional)            │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  ui/main.py + clipboard_app.py (Frontend)           │  │
│  ├─────────────────────────────────────────────────────┤  │
│  │ • GTK4/Adwaita UI                                   │  │
│  │ • Implements DBus methods (Activate, ShowSettings)  │  │
│  │ • WebSocket client to backend                       │  │
│  │ • Displays clipboard history                        │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  dbus_service.py (Shared Module)                    │  │
│  ├─────────────────────────────────────────────────────┤  │
│  │ • TFCBMDBusService class                            │  │
│  │ • DBus interface implementation                     │  │
│  │ • Used by both server and UI                        │  │
│  └─────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Backward Compatibility

### Unix Socket
The Unix socket server (`simple-clipboard.sock`) **remains functional** for backward compatibility. Both DBus and Unix socket can receive clipboard events simultaneously.

### WebSocket
WebSocket communication between UI and server is unchanged.

## Installation Checklist

- [ ] 1. Install GNOME extension
  ```bash
  cp -r tfcbm-gnome-extension ~/.local/share/gnome-shell/extensions/tfcbm-clipboard-monitor@github.com/
  gnome-extensions enable tfcbm-clipboard-monitor@github.com
  ```

- [ ] 2. Set up autostart
  ```bash
  cp org.tfcbm.ClipboardManager.desktop.autostart \
     ~/.config/autostart/org.tfcbm.ClipboardManager.desktop
  ```

- [ ] 3. Update paths in autostart file (if needed)
  ```bash
  nano ~/.config/autostart/org.tfcbm.ClipboardManager.desktop
  ```

- [ ] 4. Restart GNOME Shell
  - X11: Alt+F2 → 'r' → Enter
  - Wayland: Log out & log in

- [ ] 5. Verify DBus service
  ```bash
  busctl --user list | grep tfcbm
  ```

- [ ] 6. Test clipboard monitoring
  - Copy some text
  - Check `/tmp/tfcbm_server.log`
  - Should see: "Processing clipboard event via DBus"

## Testing Commands

### Check DBus Service
```bash
busctl --user list | grep tfcbm
# Should show: org.tfcbm.ClipboardManager
```

### Test Activate
```bash
busctl --user call org.tfcbm.ClipboardManager \
    /org/tfcbm/ClipboardManager \
    org.tfcbm.ClipboardManager \
    Activate u 0
```

### Test OnClipboardChange
```bash
busctl --user call org.tfcbm.ClipboardManager \
    /org/tfcbm/ClipboardManager \
    org.tfcbm.ClipboardManager \
    OnClipboardChange s '{"type":"text","data":"Test from DBus"}'
```

### Monitor DBus Traffic
```bash
dbus-monitor --session "interface='org.tfcbm.ClipboardManager'"
```

## Known Issues & Limitations

### 1. Autostart Paths
The `.desktop` file uses absolute paths. Update them if TFCBM is installed in a different location.

### 2. GLib Dependency
The server now requires `python-gi` (GLib/GObject introspection) for DBus support.

Install if missing:
```bash
pip install PyGObject
# or
sudo dnf install python3-gobject  # Fedora
sudo apt install python3-gi        # Ubuntu
```

### 3. Thread Safety
The DBus handler uses `db_lock` for thread-safe database access, same as the Unix socket handler.

## Future Improvements

### Potential Enhancements:
1. **Remove Unix Socket**: Once fully migrated to DBus, Unix socket can be removed
2. **Systemd Service**: Create systemd user service as alternative to autostart
3. **DBus Activation**: Use DBus activation to start TFCBM on-demand
4. **Flatpak Integration**: Package TFCBM as Flatpak with proper DBus permissions

## Support

For issues or questions:
1. Check logs: `/tmp/tfcbm_server.log` and `/tmp/tfcbm_ui.log`
2. Read: `GNOME_EXTENSION_INTEGRATION.md`
3. Test DBus manually (commands above)
4. Check GNOME Shell logs: `journalctl -f -o cat /usr/bin/gnome-shell`

## Summary

✅ **Completed:**
- DBus service implementation
- Clipboard event handling via DBus
- UI window activation via DBus
- Settings page navigation via DBus
- Autostart configuration
- Comprehensive documentation

✅ **Benefits:**
- GNOME-compliant extension
- Clean separation of concerns
- Standard IPC mechanism
- Independent update cycles
- Better maintainability

✅ **Backward Compatible:**
- Unix socket still works
- WebSocket unchanged
- Existing functionality preserved
