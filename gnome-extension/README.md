# TFCBM Clipboard Monitor - GNOME Shell Extension

A GNOME Shell extension that monitors clipboard changes and integrates with the TFCBM (The Fucking Clipboard Manager) application.

## Features

- 📋 **Clipboard Monitoring**: Automatically monitors clipboard changes for text, images, and files
- ⌨️ **Keyboard Shortcut**: Quick access to TFCBM UI with configurable keyboard shortcut (default: Ctrl+Escape)
- 🎯 **System Tray Integration**: Tray icon for easy access to TFCBM functionality
- 🔌 **DBus Communication**: Uses standard DBus for secure communication with TFCBM app

## Privacy & Security

This extension accesses clipboard content to monitor changes. **All clipboard data is only sent to the TFCBM application running locally on your system via DBus**. No data is sent to external servers or third parties.

## Requirements

- GNOME Shell 43, 44, 45, 46, 47, 48, or 49
- TFCBM application (installed separately)

## Installation

### From extensions.gnome.org (Recommended)

1. Visit [extensions.gnome.org](https://extensions.gnome.org/)
2. Search for "TFCBM Clipboard Monitor"
3. Click the toggle to install
4. Install the TFCBM application separately

### Manual Installation

1. Download or clone this repository
2. Copy the extension directory to `~/.local/share/gnome-shell/extensions/`:
   ```bash
   cp -r . ~/.local/share/gnome-shell/extensions/tfcbm-clipboard-monitor@github.com
   ```
3. Restart GNOME Shell:
   - On X11: Press `Alt+F2`, type `r`, and press Enter
   - On Wayland: Log out and log back in
4. Enable the extension:
   ```bash
   gnome-extensions enable tfcbm-clipboard-monitor@github.com
   ```

## Usage

### With TFCBM Application

1. **Install TFCBM**: Install the TFCBM application separately (via Flatpak, package manager, or from source)
2. **Start TFCBM**: The TFCBM app can be configured to auto-start on login
3. **Use the Extension**:
   - Click the tray icon to open TFCBM UI
   - Press the keyboard shortcut (Ctrl+Escape) to toggle TFCBM UI
   - Right-click tray icon for additional options

### Without TFCBM Application

The extension will still monitor clipboard changes, but UI controls won't work until TFCBM app is running. The extension gracefully handles the case when TFCBM is not running.

## Configuration

### Keyboard Shortcut

To change the keyboard shortcut using `dconf-editor`:
```bash
dconf write /org/gnome/shell/extensions/simple-clipboard/toggle-tfcbm-ui "['<Super><Shift>C']"
```

## Troubleshooting

### Extension not working

1. Check if extension is enabled:
   ```bash
   gnome-extensions list --enabled
   ```

2. Check for errors:
   ```bash
   journalctl -f -o cat /usr/bin/gnome-shell
   ```

3. Restart GNOME Shell (X11 only):
   - Press `Alt+F2`, type `r`, press Enter

### TFCBM UI not opening

- Ensure TFCBM application is installed and running
- Check if TFCBM's DBus service is registered:
  ```bash
  busctl --user list | grep tfcbm
  ```

## Integration with TFCBM Application

This extension communicates with the TFCBM application using DBus. The TFCBM app must implement the following DBus interface:

- **Service**: `org.tfcbm.ClipboardManager`
- **Path**: `/org/tfcbm/ClipboardManager`
- **Interface**: `org.tfcbm.ClipboardManager`

### Required DBus Methods

- `Activate(u: timestamp)` - Brings TFCBM window to foreground
- `ShowSettings(u: timestamp)` - Opens TFCBM settings
- `Quit()` - Quits the TFCBM application
- `OnClipboardChange(s: eventData)` - Receives clipboard change notifications

## Development

### File Structure

```
tfcbm-gnome-extension/
├── extension.js              # Main extension code
├── metadata.json             # Extension metadata
├── tfcbm.svg                # Extension icon
├── schemas/                  # GSettings schemas
│   └── org.gnome.shell.extensions.simple-clipboard.gschema.xml
└── src/                     # Source modules
    ├── ClipboardMonitorService.js
    ├── PollingScheduler.js
    ├── adapters/
    │   ├── DBusNotifier.js
    │   └── GnomeClipboardAdapter.js
    └── domain/
        ├── ClipboardEvent.js
        ├── ClipboardPort.js
        └── NotificationPort.js
```

### Building & Testing

```bash
# Install to local extensions directory
cp -r . ~/.local/share/gnome-shell/extensions/tfcbm-clipboard-monitor@github.com

# View logs
journalctl -f -o cat /usr/bin/gnome-shell

# Enable extension
gnome-extensions enable tfcbm-clipboard-monitor@github.com
```

## License

GPL-2.0-or-later (see LICENSE file)

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## Links

- TFCBM Application: [Update with actual GitHub repository URL]
- Report Issues: [Update with actual GitHub issues URL]
- GNOME Extensions: https://extensions.gnome.org/

## Acknowledgments

This extension follows GNOME Shell Extension guidelines and best practices.
