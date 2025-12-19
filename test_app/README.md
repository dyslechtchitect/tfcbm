# Shortcut Recorder POC

A proof-of-concept application demonstrating proper keyboard shortcut handling and window focus-stealing on GNOME/Wayland using **GApplication Actions**.

## What This Demonstrates

This POC shows the **correct way** to implement global keyboard shortcuts that can steal window focus on Wayland without triggering "Window is ready" notifications.

### The Solution: GApplication Actions + GNOME Shell Extension

Unlike custom DBus methods or the xdg-desktop-portal API, this approach uses:

1. **GApplication Actions** (`org.gtk.Actions.Activate`)
2. **GNOME Shell Extension** to bind the keyboard shortcut
3. **Standard DBus interface** for action invocation

## How It Works

### 1. Python GTK4 Application (`main.py`)

The application registers a GAction called `show-window`:

```python
show_action = Gio.SimpleAction.new("show-window", None)
show_action.connect("activate", self._on_show_window_action)
self.add_action(show_action)
```

This action is **automatically exposed via DBus** at:
- **Interface**: `org.gtk.Actions`
- **Method**: `Activate`
- **Parameters**: `(action_name, parameters, platform_data)`

### 2. GNOME Shell Extension (`gnome-extension/`)

The extension:
- Registers the keyboard shortcut (`Ctrl+Shift+K`)
- Listens for the shortcut press
- Invokes the GAction via DBus:

```javascript
Gio.DBus.session.call(
    'org.example.ShortcutRecorder',
    '/org/example/ShortcutRecorder',
    'org.gtk.Actions',
    'Activate',
    new GLib.Variant('(sava{sv})', ['show-window', [], {}]),
    ...
);
```

### 3. Why This Works on Wayland

**GApplication actions are privileged**:
- GNOME/Wayland recognizes `org.gtk.Actions` as a legitimate application activation interface
- The compositor trusts these calls because they come from the Shell's event context
- Focus-stealing permission is granted automatically
- No "Window is ready" notification appears

## Installation

```bash
cd test_app
./install.sh
```

## Usage

1. Start the application:
   ```bash
   ./main.py
   ```

2. Press `Ctrl+Shift+K` anywhere (even when the window is hidden or minimized)

3. The window will appear and **immediately gain focus** - no notification!

## Uninstallation

```bash
cd test_app
./uninstall.sh
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    GNOME Shell (Wayland)                    │
│  ┌────────────────────────────────────────────────────┐     │
│  │  Extension: Keyboard Shortcut Handler              │     │
│  │  - Registers Ctrl+Shift+K                          │     │
│  │  - Calls org.gtk.Actions.Activate via DBus         │     │
│  └────────────────┬───────────────────────────────────┘     │
└───────────────────┼─────────────────────────────────────────┘
                    │ DBus (Session Bus)
                    │ org.gtk.Actions.Activate
                    │
┌───────────────────▼─────────────────────────────────────────┐
│              Python GTK4 Application                        │
│  ┌────────────────────────────────────────────────────┐     │
│  │  GApplication                                      │     │
│  │  - Exposes 'show-window' action via DBus          │     │
│  │  - Action handler: toggle window visibility        │     │
│  │  - Window.present() → FOCUS GRANTED ✓              │     │
│  └────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

## Key Differences from Failed Approaches

| Approach | Why It Failed | This Solution |
|----------|---------------|---------------|
| Custom DBus method | Lost activation context | Uses standard `org.gtk.Actions` |
| `present_with_time()` | Timestamp not sufficient | GAction preserves Shell context |
| xdg-desktop-portal | Requires user permission | Automatic via GNOME Shell |
| Direct `gtk-launch` | Activates existing instance without context | GAction called from Shell |

## Files

- `main.py` - GTK4/Libadwaita application with GAction
- `gnome-extension/extension.js` - GNOME Shell extension
- `gnome-extension/metadata.json` - Extension metadata
- `gnome-extension/schemas/*.gschema.xml` - GSettings schema for keybinding
- `install.sh` - Installation script
- `uninstall.sh` - Uninstallation script

## Requirements

- GNOME Shell 45+ (tested on 49.2)
- Python 3.10+
- GTK 4.0
- Libadwaita 1
- PyGObject

## Testing

After installation:

1. Run `./main.py`
2. Minimize or hide the window
3. Press `Ctrl+Shift+K`
4. Window should appear AND gain focus immediately
5. Check the counter increments each time
6. No "Window is ready" notification should appear

## Notes

- The extension may require a GNOME Shell restart after installation
- Use `Alt+F2`, type `r`, press Enter to restart Shell (X11 only)
- On Wayland, log out and back in
- Check extension status: `gnome-extensions list`
- View logs: `journalctl -f -o cat /usr/bin/gnome-shell`
