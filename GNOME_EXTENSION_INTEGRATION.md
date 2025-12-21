# TFCBM GNOME Extension Integration Guide

This guide explains how to set up TFCBM to work with the decoupled GNOME Shell extension.

## Architecture

The TFCBM system now uses a **decoupled architecture** where the extension and application communicate via DBus:

```
┌──────────────────────────┐         ┌────────────────────────────┐
│  GNOME Extension         │         │  TFCBM Application         │
│  (gnome-shell process)   │  DBus   │  (independent process)     │
├──────────────────────────┤◄───────►├────────────────────────────┤
│ • Monitors clipboard     │         │ • Registers DBus service   │
│ • Tray icon & shortcuts  │         │ • Stores clipboard data    │
│ • Sends events via DBus  │         │ • Shows UI window          │
└──────────────────────────┘         └────────────────────────────┘
```

## What Changed

### Before (Non-Compliant)
- Extension launched Python processes
- Extension killed Python processes
- Unix socket communication
- Hardcoded paths

### After (GNOME-Compliant)
- ✅ Extension only communicates via DBus
- ✅ TFCBM starts independently (autostart)
- ✅ DBus for all IPC
- ✅ No hardcoded paths in extension

## Installation Steps

### 1. Install the GNOME Extension

**Option A: From extensions.gnome.org (Recommended)**
```bash
# Visit extensions.gnome.org and search for "TFCBM Clipboard Monitor"
# Click install
```

**Option B: Manual Installation**
```bash
cd /home/ron/Documents/git/tfcbm-gnome-extension
cp -r . ~/.local/share/gnome-shell/extensions/tfcbm-clipboard-monitor@github.com/
gnome-extensions enable tfcbm-clipboard-monitor@github.com
```

### 2. Set Up Auto-Start for TFCBM

Copy the autostart file to your autostart directory:

```bash
cd /home/ron/Documents/git/TFCBM
cp org.tfcbm.ClipboardManager.desktop.autostart ~/.config/autostart/org.tfcbm.ClipboardManager.desktop
```

### 3. Restart GNOME Shell

**On X11:**
```bash
# Press Alt+F2, type 'r', press Enter
```

**On Wayland:**
```bash
# Log out and log back in
```

### 4. Verify Integration

Check if TFCBM's DBus service is registered:

```bash
busctl --user list | grep tfcbm
```

You should see:
```
org.tfcbm.ClipboardManager
```

## DBus Interface

The TFCBM server now implements these DBus methods:

### Service Details
- **Bus Name**: `org.tfcbm.ClipboardManager`
- **Object Path**: `/org/tfcbm/ClipboardManager`
- **Interface**: `org.tfcbm.ClipboardManager`

### Methods

#### `Activate(u: timestamp)`
Toggles the TFCBM window visibility.
```bash
# Test it:
busctl --user call org.tfcbm.ClipboardManager \
    /org/tfcbm/ClipboardManager \
    org.tfcbm.ClipboardManager \
    Activate u 0
```

#### `ShowSettings(u: timestamp)`
Opens the TFCBM settings page.
```bash
busctl --user call org.tfcbm.ClipboardManager \
    /org/tfcbm/ClipboardManager \
    org.tfcbm.ClipboardManager \
    ShowSettings u 0
```

#### `Quit()`
Quits the TFCBM application.
```bash
busctl --user call org.tfcbm.ClipboardManager \
    /org/tfcbm/ClipboardManager \
    org.tfcbm.ClipboardManager \
    Quit
```

#### `OnClipboardChange(s: eventData)`
Receives clipboard events from the extension (called automatically).

**Event Format:**
```json
{
  "type": "text|image/png|image/jpeg|file",
  "data": "content or base64 data",
  "formattedContent": "optional base64 HTML/RTF",
  "formatType": "html|rtf"
}
```

## Files Modified

### New Files Created:
1. **`dbus_service.py`** - Reusable DBus service module
2. **`org.tfcbm.ClipboardManager.desktop.autostart`** - Autostart configuration

### Modified Files:
1. **`tfcbm_server.py`**
   - Added `handle_clipboard_event_dbus()` function
   - Integrated DBus service in separate thread
   - Keeps Unix socket for backward compatibility

2. **`ui/application/clipboard_app.py`**
   - Now uses `TFCBMDBusService` from `dbus_service.py`
   - Simplified DBus handling

## Testing

### 1. Test TFCBM Startup
```bash
cd /home/ron/Documents/git/TFCBM
./launcher.py
```

Check logs:
```bash
tail -f /tmp/tfcbm_server.log
tail -f /tmp/tfcbm_ui.log
```

You should see:
```
✓ DBus service started for GNOME extension integration
```

### 2. Test Extension Communication

**Copy some text**, then check server log:
```bash
tail -f /tmp/tfcbm_server.log
```

You should see:
```
Processing clipboard event via DBus: text
✓ Copied text (XX chars)
```

### 3. Test Tray Icon
- Click the TFCBM tray icon → Window should toggle
- Right-click → Menu should appear
- Click "TFCBM Settings" → Settings page should open
- Click "Quit TFCBM App" → App should quit

### 4. Test Keyboard Shortcut
Default: `Ctrl+Escape`

Press the shortcut → TFCBM window should toggle

## Troubleshooting

### Extension Not Working

**Check if extension is enabled:**
```bash
gnome-extensions list --enabled | grep tfcbm
```

**Check for errors:**
```bash
journalctl -f -o cat /usr/bin/gnome-shell | grep -i tfcbm
```

### TFCBM Not Receiving Clipboard Events

**1. Check if DBus service is registered:**
```bash
busctl --user list | grep tfcbm
```

**2. Check if server is running:**
```bash
pgrep -af tfcbm_server.py
```

**3. Check server logs:**
```bash
tail -100 /tmp/tfcbm_server.log
```

### DBus Service Not Registering

**Check for conflicts:**
```bash
# Kill any existing instances
pkill -9 -f tfcbm_server.py
pkill -9 -f "ui/main.py"

# Restart
./launcher.py
```

### Keyboard Shortcut Not Working

**Check GSettings:**
```bash
dconf read /org/gnome/shell/extensions/simple-clipboard/toggle-tfcbm-ui
```

**Change shortcut:**
```bash
dconf write /org/gnome/shell/extensions/simple-clipboard/toggle-tfcbm-ui "['<Super><Shift>C']"
```

## Uninstalling

### Remove Extension
```bash
gnome-extensions disable tfcbm-clipboard-monitor@github.com
rm -rf ~/.local/share/gnome-shell/extensions/tfcbm-clipboard-monitor@github.com/
```

### Remove Autostart
```bash
rm ~/.config/autostart/org.tfcbm.ClipboardManager.desktop
```

### Stop TFCBM
```bash
pkill -f tfcbm_server.py
pkill -f "ui/main.py"
```

## Development & Debugging

### Monitor DBus Traffic
```bash
dbus-monitor --session "interface='org.tfcbm.ClipboardManager'"
```

### Test DBus Methods Manually
```bash
# Test OnClipboardChange
busctl --user call org.tfcbm.ClipboardManager \
    /org/tfcbm/ClipboardManager \
    org.tfcbm.ClipboardManager \
    OnClipboardChange s '{"type":"text","data":"Hello from DBus!"}'
```

### Enable Debug Logging
In `tfcbm_server.py`, change:
```python
logging.basicConfig(level=logging.DEBUG, ...)
```

## Benefits of New Architecture

### For Users:
- ✅ Extension can be installed from extensions.gnome.org
- ✅ TFCBM and extension update independently
- ✅ More reliable (standard DBus IPC)
- ✅ Works with GNOME's security model

### For Developers:
- ✅ Cleaner code separation
- ✅ Easier to maintain
- ✅ Follows GNOME best practices
- ✅ No policy violations

## Support

If you encounter issues:
1. Check logs: `/tmp/tfcbm_server.log` and `/tmp/tfcbm_ui.log`
2. Check GNOME Shell logs: `journalctl -f -o cat /usr/bin/gnome-shell`
3. Verify DBus service: `busctl --user list | grep tfcbm`
4. Test DBus methods manually (see above)
