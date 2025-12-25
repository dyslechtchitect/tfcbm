# TFCBM - The Fucking Clipboard Manager

A powerful, feature-rich clipboard manager for GNOME with seamless desktop integration.

![License](https://img.shields.io/badge/license-GPL--3.0-blue.svg)
![GNOME Shell](https://img.shields.io/badge/GNOME%20Shell-43--49-blue.svg)
![Python](https://img.shields.io/badge/python-3.10+-blue.svg)

## Features

🎯 **Core Features**
- 📋 Unlimited clipboard history tracking
- 🖼️ Support for text, images, and files
- 🔍 Fast search and filtering
- 🏷️ Tag organization system
- 🔐 Secure storage for sensitive data
- ⌨️ Keyboard shortcuts for quick access
- 🎨 Beautiful GTK4/Libadwaita interface

🔌 **Desktop Integration**
- Optional GNOME Shell extension for system-wide monitoring
- DBus integration for seamless communication
- System tray integration
- Global keyboard shortcut (Ctrl+Escape)

## Screenshots

<!-- Add your screenshots here once you create them -->
*Screenshots coming soon*

## Installation

### From Flathub (Recommended - Coming Soon)

```bash
flatpak install flathub org.tfcbm.ClipboardManager
```

### GNOME Extension

The GNOME Shell extension is available on [extensions.gnome.org](https://extensions.gnome.org/) (Coming Soon)

Or install manually from the app:
```bash
tfcbm-install-extension
```

### From Source

#### Prerequisites

- Python 3.10+
- GTK 4
- Libadwaita
- GNOME Shell 43+ (for extension)

**System dependencies:**
```bash
# Fedora
sudo dnf install python3 python3-pip gtk4 libadwaita python3-gobject

# Debian/Ubuntu
sudo apt install python3 python3-pip libgtk-4-1 libadwaita-1-0 python3-gi
```

#### Installation Steps

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/tfcbm.git
   cd tfcbm
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application:**
   ```bash
   python3 ui/main.py
   ```

4. **Install the GNOME Extension (Optional):**
   ```bash
   cd gnome-extension
   ./install.sh
   ```

## Usage

### Starting TFCBM

**From Flatpak:**
```bash
flatpak run org.tfcbm.ClipboardManager
```

**From source:**
```bash
python3 ui/main.py
```

### Keyboard Shortcuts

- **Ctrl+Escape** - Show/hide clipboard manager (when extension is installed)
- **Ctrl+F** - Search clipboard history (in app)
- **Enter** - Paste selected item
- **Delete** - Remove item from history

### Using Tags

1. Right-click on any clipboard item
2. Select "Add Tag"
3. Enter tag name
4. Filter by tags using the tag filter bar

### Secure Items

Store passwords and sensitive data securely:
1. Right-click on an item
2. Select "Mark as Secret"
3. Enter a name for the secret
4. Item will be encrypted and stored securely

## GNOME Extension

The optional GNOME Shell extension provides:
- Automatic clipboard monitoring
- Global keyboard shortcut
- System tray integration
- Real-time sync with the main app

**Supported GNOME Shell versions:** 43, 44, 45, 46, 47, 48, 49

### Extension Installation

**Option 1: From extensions.gnome.org** (Coming Soon)
1. Visit [extensions.gnome.org](https://extensions.gnome.org/)
2. Search for "TFCBM Clipboard Monitor"
3. Click install

**Option 2: Manual installation**
```bash
cd gnome-extension
./install.sh
gnome-extensions enable tfcbm-clipboard-monitor@github.com
```

## Configuration

### Settings

Access settings through the app's preferences:
- Clipboard history limit
- Auto-start on login
- Keyboard shortcuts
- Extension integration
- Storage location

### Database

TFCBM stores clipboard history in an SQLite database:
- Location: `~/.local/share/tfcbm/clipboard.db`
- Automatic cleanup of old items
- Encrypted storage for secrets

## Development

### Project Structure

```
TFCBM/
├── ui/                          # GTK4 application code
│   ├── application/            # Main application
│   ├── components/             # UI components
│   ├── managers/               # Business logic managers
│   ├── services/               # Core services
│   └── windows/                # Window definitions
├── gnome-extension/            # GNOME Shell extension
│   ├── extension.js           # Extension entry point
│   ├── src/                   # Extension source code
│   └── schemas/               # GSettings schemas
├── database.py                 # Database management
├── dbus_service.py            # DBus service
├── tfcbm_server.py            # Backend server
└── requirements.txt           # Python dependencies
```

### Building from Source

See [DEVELOPMENT.md](DEVELOPMENT.md) for detailed development instructions.

### Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Flatpak Packaging

For packaging and submission instructions, see:
- [README_PACKAGING.md](README_PACKAGING.md) - Packaging overview
- [FLATPAK_SUBMISSION_GUIDE.md](FLATPAK_SUBMISSION_GUIDE.md) - Submission guide
- [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md) - Pre-release checklist

## Privacy & Security

**What data is collected?**
- None. TFCBM operates entirely locally on your system.

**Clipboard monitoring:**
- The extension monitors clipboard changes to track history
- All clipboard data stays on your local machine
- Data is sent only to the TFCBM app via local DBus (no network)

**Secure storage:**
- Sensitive items are encrypted using system keyring
- Passwords never leave your machine
- Database is stored locally

## Troubleshooting

### Extension not working

```bash
# Check extension status
gnome-extensions list
gnome-extensions info tfcbm-clipboard-monitor@github.com

# View logs
journalctl -f /usr/bin/gnome-shell

# Restart GNOME Shell
# X11: Alt+F2, type 'r', press Enter
# Wayland: Log out and log back in
```

### App won't start

```bash
# Check for errors
python3 ui/main.py

# Verify dependencies
pip install -r requirements.txt

# Check DBus service
ps aux | grep tfcbm
```

### Database issues

```bash
# Reset database (WARNING: This deletes all history)
rm ~/.local/share/tfcbm/clipboard.db

# Restart the app
python3 ui/main.py
```

## System Requirements

- **OS**: Linux (GNOME desktop environment)
- **GNOME Shell**: 43 or later (for extension)
- **Python**: 3.10 or later
- **GTK**: 4.0+
- **Libadwaita**: 1.0+

## License

This project is licensed under the GNU General Public License v3.0 or later - see the [LICENSE](LICENSE) file for details.

## Credits

- **Developer**: TFCBM Developers
- **Built with**: GTK4, Libadwaita, Python, GJS
- **Icon**: [Add attribution if using third-party icons]

## Links

- **Homepage**: https://github.com/yourusername/tfcbm
- **Bug Reports**: https://github.com/yourusername/tfcbm/issues
- **Flathub**: https://flathub.org/apps/org.tfcbm.ClipboardManager (Coming Soon)
- **Extensions**: https://extensions.gnome.org/ (Coming Soon)

## Support

- 🐛 **Report bugs**: [GitHub Issues](https://github.com/yourusername/tfcbm/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/yourusername/tfcbm/discussions)
- 📧 **Email**: [Your email]

---

**Made with ❤️ for the GNOME community**

*TFCBM - Because managing your clipboard shouldn't be a pain in the ass.*
