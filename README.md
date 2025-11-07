# TFCBM - The F*cking Clipboard Manager

A clipboard history manager for GNOME Wayland that actually works.

## How It Works

This uses a **two-part solution** to work around GNOME Wayland's clipboard security:

1. **GNOME Shell Extension** (GJS) - Runs inside GNOME Shell with clipboard access, monitors changes every 250ms
2. **Python Server** - Receives clipboard data via UNIX socket and maintains history

## Quick Start

### 0. Install Dependencies (First Time Only)

```bash
./install.sh
```

This installs system dependencies including `grim` for screenshot capture.

### 1. Install the GNOME Shell Extension

```bash
./install_extension.sh
```

Then restart GNOME Shell (log out and back in on Wayland).

### 2. Start the Python Server

```bash
python3 tfcbm_server.py
```

### 3. Test It

Copy some text and watch it appear in the terminal!
Screenshots are captured automatically every 30 seconds.

## Manual Installation

If the install script doesn't work:

```bash
# Install extension
mkdir -p ~/.local/share/gnome-shell/extensions/simple-clipboard@tfcbm
cp gnome-extension/* ~/.local/share/gnome-shell/extensions/simple-clipboard@tfcbm/

# Enable it
gnome-extensions enable simple-clipboard@tfcbm

# Restart GNOME Shell (Wayland: log out/in)
```

## Features

- ✓ Event-driven clipboard monitoring (250ms polling inside GNOME Shell)
- ✓ Automatic screenshot capture every 30 seconds (configurable)
- ✓ No interference with browser context menus
- ✓ Works on GNOME Wayland
- ✓ Text clipboard support
- ✓ Image clipboard support
- ✓ Screenshot logging to history
- ✓ Optional screenshot saving to disk
- ✓ Simple UNIX socket IPC

## Why This Approach?

GNOME Wayland has strict clipboard security - background apps can't access the clipboard. We tried:

- ❌ PyGObject/GTK3 - Returns `None` for background apps
- ❌ `wl-paste --watch` - Requires wlroots protocol (GNOME doesn't support it)
- ❌ Polling with `wl-paste` - Interferes with Chrome/Firefox right-click menus

**Solution**: Run monitoring code inside GNOME Shell itself, where clipboard access is allowed!

## Files

- `gnome-extension/` - GNOME Shell extension source
  - `extension.js` - Main extension code (~90 lines)
  - `metadata.json` - Extension metadata
  - `README.md` - Extension docs
- `tfcbm_server.py` - Python server that receives clipboard events
- `install_extension.sh` - One-command installation
- `tfcbm.py` - Old polling-based version (deprecated)

## Troubleshooting

**Extension not loading?**
```bash
# Check if it's enabled
gnome-extensions list --enabled | grep simple-clipboard

# View errors
journalctl -f -o cat /usr/bin/gnome-shell
```

**Server not receiving data?**
- Make sure extension is installed and GNOME Shell is restarted
- Check socket exists: `ls $XDG_RUNTIME_DIR/simple-clipboard.sock`
- Extension silently fails if socket doesn't exist (start server first)

**Still having issues?**
- Verify GNOME Shell version matches metadata.json (43-47)
- Check file permissions in extension directory

## Screenshot Feature

Screenshots are automatically captured every 30 seconds and added to clipboard history.

**Configure in tfcbm_server.py:**
```python
SCREENSHOT_INTERVAL = 30  # seconds between screenshots
SCREENSHOT_ENABLED = True  # set to False to disable
SCREENSHOT_SAVE_DIR = './screenshots'  # uncomment to save to disk
```

See **SCREENSHOT_FEATURE.md** for full documentation.

## Future Ideas

- [ ] Save history to disk (JSON export)
- [ ] GUI for browsing history
- [ ] Clipboard search
- [ ] D-Bus interface instead of UNIX socket
- [ ] History size limits
- [ ] Screenshot area/window selection

## License

Do whatever you want with it.
