# Simple Clipboard Monitor - GNOME Shell Extension

A minimal GNOME Shell extension that monitors clipboard changes and sends them to a UNIX socket.

## Installation

1. Create the extension directory:
```bash
mkdir -p ~/.local/share/gnome-shell/extensions/simple-clipboard@tfcbm
```

2. Copy the files:
```bash
cp extension.js metadata.json ~/.local/share/gnome-shell/extensions/simple-clipboard@tfcbm/
```

3. Enable the extension:
```bash
gnome-extensions enable simple-clipboard@tfcbm
```

4. Restart GNOME Shell:
   - On X11: Press `Alt+F2`, type `r`, press Enter
   - On Wayland: Log out and log back in (or reboot)

## Verify Installation

Check if the extension is running:
```bash
gnome-extensions list --enabled | grep simple-clipboard
```

View logs:
```bash
journalctl -f -o cat /usr/bin/gnome-shell
```

## Usage

The extension sends clipboard data to a UNIX socket at:
```
$XDG_RUNTIME_DIR/simple-clipboard.sock
```

Create a Python server to receive the data (see ../tfcbm_server.py)

## Uninstall

```bash
gnome-extensions disable simple-clipboard@tfcbm
rm -rf ~/.local/share/gnome-shell/extensions/simple-clipboard@tfcbm
```

## How it Works

- Polls clipboard every 250ms using `St.Clipboard`
- Detects changes in text content
- Sends JSON messages to UNIX socket: `{"type": "text", "content": "..."}`
- Non-blocking: If socket doesn't exist, silently continues
- Image support available (commented out by default)

## Troubleshooting

If the extension doesn't load:
1. Check GNOME Shell version matches metadata.json
2. View errors: `journalctl -f -o cat /usr/bin/gnome-shell`
3. Ensure files have correct permissions
4. Try restarting GNOME Shell
