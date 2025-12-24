# TFCBM Application Integration Guide

This guide explains how to integrate the TFCBM application with the GNOME extension for proper decoupled operation.

## Architecture Overview

The extension and application are now **decoupled** and communicate only via DBus:

```
┌─────────────────────────────┐         ┌──────────────────────────┐
│  GNOME Extension            │         │  TFCBM Application       │
│  (GNOME Shell process)      │         │  (Separate process)      │
├─────────────────────────────┤         ├──────────────────────────┤
│ • Monitors clipboard        │         │ • Registers DBus service │
│ • Manages tray icon         │  DBus   │ • Stores clipboard data  │
│ • Handles keyboard shortcut │◄───────►│ • Shows UI window        │
│ • Sends clipboard events    │         │ • Manages settings       │
└─────────────────────────────┘         └──────────────────────────┘
```

## Required Changes to TFCBM Application

### 1. DBus Service Registration

The TFCBM app must register a DBus service on startup.

**Service Details:**
- **Bus Name**: `org.tfcbm.ClipboardManager`
- **Object Path**: `/org/tfcbm/ClipboardManager`
- **Interface**: `org.tfcbm.ClipboardManager`

### 2. Required DBus Methods

Implement these DBus methods in your application:

#### `Activate(u: timestamp) → void`
Brings the TFCBM window to the foreground.

**Parameters:**
- `timestamp` (uint32): X11 timestamp for focus stealing prevention

**Python Example:**
```python
def Activate(self, timestamp):
    """Bring window to foreground"""
    self.window.present_with_time(timestamp)
```

#### `ShowSettings(u: timestamp) → void`
Opens the TFCBM settings/preferences dialog.

**Parameters:**
- `timestamp` (uint32): X11 timestamp

**Python Example:**
```python
def ShowSettings(self, timestamp):
    """Show settings dialog"""
    self.settings_window.present_with_time(timestamp)
```

#### `Quit() → void`
Gracefully quits the TFCBM application.

**Python Example:**
```python
def Quit(self):
    """Quit the application"""
    self.app.quit()
```

#### `OnClipboardChange(s: eventData) → void`
Receives clipboard change events from the extension.

**Parameters:**
- `eventData` (string): JSON-encoded clipboard event

**Event Format:**
```json
{
  "type": "text|image/png|image/jpeg|file",
  "data": "clipboard content or base64 image data",
  "formattedContent": "optional HTML/RTF content",
  "formatType": "html|rtf",
  "timestamp": 1234567890
}
```

**Python Example:**
```python
def OnClipboardChange(self, eventData):
    """Handle clipboard change from extension"""
    import json
    event = json.loads(eventData)

    if event['type'] == 'text':
        self.store_text_clip(event['data'])
    elif event['type'].startswith('image/'):
        self.store_image_clip(event['data'], event['type'])
    elif event['type'] == 'file':
        self.store_file_clip(event['data'])
```

### 3. DBus Implementation (Python + GDBus)

Here's a complete example using Python and GLib's DBus:

```python
from gi.repository import Gio, GLib

DBUS_XML = """
<!DOCTYPE node PUBLIC
 "-//freedesktop//DTD D-BUS Object Introspection 1.0//EN"
 "http://www.freedesktop.org/standards/dbus/1.0/introspect.dtd">
<node>
  <interface name="org.tfcbm.ClipboardManager">
    <method name="Activate">
      <arg type="u" name="timestamp" direction="in"/>
    </method>
    <method name="ShowSettings">
      <arg type="u" name="timestamp" direction="in"/>
    </method>
    <method name="Quit"/>
    <method name="OnClipboardChange">
      <arg type="s" name="eventData" direction="in"/>
    </method>
  </interface>
</node>
"""

class TFCBMDBusService:
    def __init__(self, app):
        self.app = app
        self.owner_id = None

    def start(self):
        """Register DBus service"""
        self.owner_id = Gio.bus_own_name(
            Gio.BusType.SESSION,
            'org.tfcbm.ClipboardManager',
            Gio.BusNameOwnerFlags.NONE,
            self.on_bus_acquired,
            None,  # on_name_acquired
            None   # on_name_lost
        )

    def stop(self):
        """Unregister DBus service"""
        if self.owner_id:
            Gio.bus_unown_name(self.owner_id)

    def on_bus_acquired(self, connection, name):
        """Called when bus is acquired"""
        introspection = Gio.DBusNodeInfo.new_for_xml(DBUS_XML)
        connection.register_object(
            '/org/tfcbm/ClipboardManager',
            introspection.interfaces[0],
            self.handle_method_call,
            None,  # get_property
            None   # set_property
        )

    def handle_method_call(self, connection, sender, object_path,
                          interface_name, method_name, parameters,
                          invocation):
        """Handle incoming DBus method calls"""
        try:
            if method_name == 'Activate':
                timestamp = parameters.unpack()[0]
                self.app.activate_window(timestamp)
                invocation.return_value(None)

            elif method_name == 'ShowSettings':
                timestamp = parameters.unpack()[0]
                self.app.show_settings(timestamp)
                invocation.return_value(None)

            elif method_name == 'Quit':
                self.app.quit()
                invocation.return_value(None)

            elif method_name == 'OnClipboardChange':
                event_data = parameters.unpack()[0]
                self.app.handle_clipboard_event(event_data)
                invocation.return_value(None)

        except Exception as e:
            invocation.return_error_literal(
                Gio.io_error_quark(),
                Gio.IOErrorEnum.FAILED,
                str(e)
            )
```

**Usage in your application:**
```python
class TFCBMApplication(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='org.tfcbm.ClipboardManager')
        self.dbus_service = TFCBMDBusService(self)

    def do_startup(self):
        Gtk.Application.do_startup(self)
        # Start DBus service
        self.dbus_service.start()

    def do_shutdown(self):
        # Stop DBus service
        self.dbus_service.stop()
        Gtk.Application.do_shutdown(self)
```

### 4. Auto-Start Configuration

Create a `.desktop` file for auto-starting TFCBM on login:

**File:** `~/.config/autostart/tfcbm.desktop`
```desktop
[Desktop Entry]
Type=Application
Name=TFCBM Clipboard Manager
Exec=/path/to/tfcbm
X-GNOME-Autostart-enabled=true
Hidden=false
```

**Or use a systemd user service:**

**File:** `~/.config/systemd/user/tfcbm.service`
```ini
[Unit]
Description=TFCBM Clipboard Manager
After=graphical-session.target

[Service]
Type=simple
ExecStart=/path/to/tfcbm
Restart=on-failure

[Install]
WantedBy=default.target
```

Enable and start:
```bash
systemctl --user enable tfcbm.service
systemctl --user start tfcbm.service
```

## Testing the Integration

### 1. Test DBus Service Registration
```bash
# Check if service is registered
busctl --user list | grep tfcbm

# Introspect the service
busctl --user introspect org.tfcbm.ClipboardManager \
    /org/tfcbm/ClipboardManager
```

### 2. Test DBus Methods
```bash
# Test Activate
busctl --user call org.tfcbm.ClipboardManager \
    /org/tfcbm/ClipboardManager \
    org.tfcbm.ClipboardManager \
    Activate u 0

# Test clipboard event
busctl --user call org.tfcbm.ClipboardManager \
    /org/tfcbm/ClipboardManager \
    org.tfcbm.ClipboardManager \
    OnClipboardChange s '{"type":"text","data":"test","timestamp":1234}'
```

### 3. Test Extension Integration
1. Install and enable the GNOME extension
2. Start TFCBM application
3. Copy some text
4. Verify clipboard event received by TFCBM
5. Click tray icon to activate window
6. Check TFCBM window appears

## Migration from Old Architecture

### What Changed:
1. ❌ **Removed**: Extension launching TFCBM via Python scripts
2. ❌ **Removed**: Extension killing TFCBM processes
3. ❌ **Removed**: Unix socket communication
4. ✅ **Added**: DBus service registration in TFCBM app
5. ✅ **Added**: Auto-start mechanism
6. ✅ **Changed**: Extension sends clipboard data via DBus

### Benefits:
- ✅ Extension can be submitted to extensions.gnome.org
- ✅ Cleaner separation of concerns
- ✅ More reliable IPC (DBus is standard)
- ✅ Better error handling
- ✅ Follows GNOME best practices

## Troubleshooting

### Extension tray icon does nothing when clicked
- Ensure TFCBM app is running
- Check DBus service registration: `busctl --user list | grep tfcbm`
- Check TFCBM logs for errors

### Clipboard events not received
- Verify extension is enabled: `gnome-extensions list --enabled`
- Check extension logs: `journalctl -f -o cat /usr/bin/gnome-shell`
- Test DBus method manually (see testing section above)

### TFCBM doesn't start on login
- Check autostart file exists and is executable
- Or check systemd service: `systemctl --user status tfcbm.service`

## Summary

The decoupled architecture allows:
- Extension to be distributed via extensions.gnome.org
- TFCBM app to be distributed via Flatpak/package managers
- Users to install and update each component independently
- Compliance with GNOME extension guidelines
