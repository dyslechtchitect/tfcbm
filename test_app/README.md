# Popup App - Custom Keyboard Shortcut POC

A proof-of-concept GTK4 application for Fedora 43 (Wayland) that allows users to set and manage custom keyboard shortcuts to activate the app **WITHOUT any notifications**.

## Features

- Record custom keyboard shortcuts through a GUI
- Save shortcuts via GNOME Shell extension
- Activate app via D-Bus when shortcut is pressed
- **NO notifications when using the shortcut** (Wayland compatible)
- Single-instance application

## Installation

1. Install the GNOME Shell extension:
```bash
ln -sf $(pwd)/gnome-extension ~/.local/share/gnome-shell/extensions/popup-app-hotkey@example.com
```

2. Enable the extension (choose one):
   - Open Extensions app: `gnome-extensions-app` and toggle "Popup App Hotkey" ON
   - Or log out and log back in

3. Start the application:
```bash
python3 popup_app.py
```

## Usage

1. Press **Ctrl+Shift+R** to open the app (default shortcut)
2. Click "Set New Shortcut" to enter recording mode
3. Press your desired key combination (e.g., Ctrl+Alt+K)
4. Click "Save" to apply the new shortcut
5. Click "Restore Default" to reset to Ctrl+Shift+R

## Why No Notifications?

This POC uses a **GNOME Shell extension** instead of GNOME's built-in custom-keybindings system. The extension runs inside GNOME Shell itself, allowing it to register global shortcuts without triggering Wayland's security notifications.

This is the same approach used by TFCBM and other professional GNOME applications that need global hotkeys on Wayland.

## Files

- `popup_app.py` - Main GTK4 application
- `gnome-extension/` - GNOME Shell extension for hotkey support
  - `extension.js` - Extension logic
  - `metadata.json` - Extension metadata
  - `schemas/` - GSettings schema for hotkey configuration
- `global_hotkey.py` - (Unused) X11 hotkey listener for reference
- `activate_app.sh` - (Unused) Wrapper script for reference

## Technical Details

- Uses GNOME Shell extension for global hotkey registration (Wayland compatible)
- D-Bus service name: `com.example.PopupApp`
- Default shortcut: `<Primary><Shift>R` (Ctrl+Shift+R)
- Extension settings: `org.gnome.shell.extensions.popup-app-hotkey`
- Works on both Wayland and X11
