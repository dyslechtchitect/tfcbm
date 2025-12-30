# TFCBM Extension/App Integration

## Overview

TFCBM consists of two tightly integrated components that work together as a single system:

1. **GNOME Shell Extension** - Provides clipboard monitoring, keyboard shortcut, and tray icon
2. **Flatpak App** - Provides the UI, database, and settings

## Integrated Lifecycle

The extension and app are designed to function as **one integrated system**, not as separate components:

### Startup Behavior

1. **When you launch TFCBM app:**
   - App automatically enables the GNOME extension if installed
   - Extension becomes active and starts monitoring clipboard
   - **Tray icon appears** (indicating app is running)
   - Keyboard shortcut becomes active

2. **When you quit TFCBM app:**
   - App automatically disables the GNOME extension
   - Extension stops monitoring clipboard
   - **Tray icon disappears** (indicating app is not running)
   - Keyboard shortcut is removed

### Tray Icon Behavior

**The tray icon ONLY appears when the TFCBM app is running.**

- **Extension enabled + App running** = Tray icon visible ✓
- **Extension enabled + App NOT running** = Tray icon hidden
- **Extension disabled** = Tray icon hidden

This makes the tray icon a clear indicator of whether TFCBM is active.

### Autostart ("Start on Login")

The **"Start on Login"** setting in Settings controls the entire TFCBM system:

- **Enabled**: App launches automatically when you log in
  - App auto-enables extension
  - Tray icon appears
  - System is ready to use

- **Disabled**: Nothing launches automatically
  - You must manually launch TFCBM from applications menu
  - No tray icon until you launch the app

## Why This Design?

### Before (Confusing)

- Extension could be enabled without app running
- Tray icon would be visible but greyed out
- Users couldn't tell if TFCBM was working
- "Autostart" setting only affected app, not extension

### After (Clear)

- Tray icon visibility = app is running
- No tray icon = TFCBM is not active
- "Start on Login" controls the whole system
- Users see clear visual feedback

## Implementation Details

### Extension (gnome-extension/extension.js)

```javascript
_updateIconStyle() {
    if (!this._icon || !this._indicator) return;

    if (this._dbusOwner) {
        // App is running - show tray icon
        this._indicator.visible = true;
        this._icon.remove_style_class_name('disabled');
    } else {
        // App is not running - hide tray icon
        this._indicator.visible = false;
    }
}
```

- Monitors DBus name owner `io.github.dyslechtchitect.tfcbm`
- Shows tray icon only when DBus name is owned (app is running)
- Hides tray icon when DBus name is released (app quit)

### App Launch (ui/application/clipboard_app.py)

```python
# If extension is installed but not enabled, auto-enable it
if ext_status['installed'] and not ext_status['enabled']:
    logger.info("Extension installed but not enabled - auto-enabling...")
    success, message = enable_extension()
```

- Checks extension status on startup
- Auto-enables extension if installed but disabled
- Creates seamless user experience

### App Quit (server/src/dbus_service.py)

```python
def _handle_quit(self, invocation):
    """Handle Quit method - quit the application"""
    # Disable the GNOME extension when quitting
    try:
        connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        result = connection.call_sync(
            'org.gnome.Shell.Extensions',
            '/org/gnome/Shell/Extensions',
            'org.gnome.Shell.Extensions',
            'DisableExtension',
            GLib.Variant('(s)', ('tfcbm-clipboard-monitor@github.com',)),
            ...
        )
```

- Disables extension via DBus before quitting
- Ensures clean shutdown
- Tray icon disappears when app quits

## User Experience

From the user's perspective, TFCBM behaves as **one application**:

1. **Launch TFCBM** → Tray icon appears
2. **Quit TFCBM** → Tray icon disappears
3. **Enable "Start on Login"** → TFCBM starts with tray icon when you log in
4. **Disable "Start on Login"** → Nothing happens on login

The extension is an implementation detail that users don't need to think about.

## Testing

See `ui/test_extension_behavior.py` for tests covering:

- Extension auto-enable on app launch
- Extension auto-disable on app quit
- Tray icon visibility tied to app running state
- Autostart desktop file creation/removal

## Files Modified

- `gnome-extension/extension.js` - Hide tray icon when app not running
- `ui/pages/settings_page.py` - Clarified "Start on Login" label
- `ui/test_extension_behavior.py` - Updated test documentation
- `EXTENSION_APP_INTEGRATION.md` - This documentation
