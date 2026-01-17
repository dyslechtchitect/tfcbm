# TFCBM - The * Clipboard Manager

<p align="center">
  <img src="resouces/io.github.dyslechtchitect.tfcbm.logo.png" alt="TFCBM Logo" width="128" height="128">
</p>

<p align="center">
  <strong>A powerful clipboard manager for GNOME</strong>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-GPL--3.0-blue.svg" alt="License"></a>
  <img src="https://img.shields.io/badge/GNOME-49-blue.svg" alt="GNOME 49">
  <a href="https://flathub.org/apps/io.github.dyslechtchitect.tfcbm"><img src="https://img.shields.io/flathub/v/io.github.dyslechtchitect.tfcbm" alt="Flathub"></a>
</p>

---

## About

TFCBM is a modern clipboard manager that enhances your GNOME desktop experience. Never lose track of what you copy - TFCBM keeps a complete history of your clipboard, making it easy to find and reuse content whenever you need it.

Built with GTK4 and Libadwaita, TFCBM seamlessly integrates with your GNOME desktop, providing quick access through keyboard shortcuts and a system tray icon.

## Features

✨ **Complete Clipboard History** - Track everything you copy, never lose content again
🔍 **Powerful Search** - Find anything in your clipboard history instantly
🏷️ **Tags & Organization** - Organize clips with custom tags and colors
🖼️ **Rich Media Support** - Handle text, images, files, and URLs
🔐 **Secret Items** - Mark sensitive items as secrets with password protection
⌨️ **Keyboard Shortcuts** - Fast workflow with configurable shortcuts
🎨 **Modern Interface** - Beautiful Adwaita-based UI that follows GNOME HIG
🔄 **Real-time Monitoring** - Instant clipboard detection via GNOME Shell extension
💾 **Persistent Storage** - SQLite database with automatic retention management

## Screenshots

<p align="center">
  <img src="screenshots/general.png" alt="Main window" width="600">
  <br>
  <em>Main window showing clipboard history</em>
</p>

<p align="center">
  <img src="screenshots/search.png" alt="Search functionality" width="600">
  <br>
  <em>Search through your clipboard history</em>
</p>

<p align="center">
  <img src="screenshots/settings.png" alt="Settings" width="600">
  <br>
  <em>Configure shortcuts and preferences</em>
</p>

## Installation

### From Flathub (Recommended)

<a href="https://flathub.org/apps/io.github.dyslechtchitect.tfcbm">
  <img src="https://flathub.org/api/badge?locale=en" alt="Download on Flathub" width="200">
</a>

Or via command line:

```bash
flatpak install flathub io.github.dyslechtchitect.tfcbm
```

### From Source

1. Install dependencies:
   ```bash
   sudo dnf install flatpak-builder  # Fedora
   sudo apt install flatpak-builder  # Ubuntu/Debian
   ```

2. Install Flatpak runtime:
   ```bash
   flatpak install flathub org.gnome.Platform//49 org.gnome.Sdk//49
   ```

3. Build and install:
   ```bash
   git clone https://github.com/dyslechtchitect/tfcbm.git
   cd tfcbm
   flatpak-builder --user --install --force-clean build-dir io.github.dyslechtchitect.tfcbm.yml
   ```

4. Run:
   ```bash
   flatpak run io.github.dyslechtchitect.tfcbm
   ```

## Usage

### First Run

On first launch, TFCBM will install and enable a GNOME Shell extension for clipboard monitoring. This extension provides:

- System tray icon for quick access
- Real-time clipboard monitoring
- Global keyboard shortcut (default: `Ctrl+Escape`, configurable in settings)

You may need to restart GNOME Shell (log out and back in) after first installation for the extension to activate.

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+Escape` | Toggle TFCBM window (configurable) |
| Type to search | Auto-focus search and start typing |
| `Enter` or `Space` | Paste selected item |
| Click tray icon | Toggle TFCBM window |

### Quick Tips

- **Search**: Just start typing to search your clipboard history
- **Tags**: Right-click items to add tags and organize your clips
- **Secrets**: Mark sensitive items as secrets to protect them with a password
- **Favorite Items**: Keep important items from being auto-deleted by pinning them

## Privacy & Permissions

TFCBM takes your privacy seriously:

- **Local Only**: All clipboard data is stored locally on your computer in a SQLite database
- **No Network Access**: TFCBM never connects to the internet or sends data anywhere
- **Open Source**: All code is available for review on GitHub

### Required Permissions

- **Display Access**: To show the application window
- **D-Bus**: For communication with the GNOME Shell extension
- **XDG Data/Config**: To store clipboard history and settings

All data is stored in your home directory under `.var/app/io.github.dyslechtchitect.tfcbm/` (Flatpak) or `.local/share/tfcbm/` (local install).

## How It Works

TFCBM consists of three components that work together:

1. **GNOME Shell Extension**: Monitors clipboard changes in real-time using GNOME's native clipboard API
2. **Backend Server**: Manages the clipboard database and handles all clipboard operations
3. **UI Application**: Provides the interface for viewing and managing your clipboard history

These components communicate via Unix domain sockets for fast, secure local communication.

## Development

### Prerequisites

- Python 3.11+
- GNOME 49
- Flatpak SDK (for packaging)

### Setup

```bash
# Clone the repository
git clone https://github.com/dyslechtchitect/tfcbm.git
cd tfcbm

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Running from Source

```bash
# Terminal 1: Run the backend server
python3 main.py

# Terminal 2: Run the UI
python3 ui/main.py
```

### Testing

```bash
# Server tests
cd server
../.venv/bin/pytest test/integration -v

# Extension tests
cd gnome-extension
npm test
```

### Building Flatpak

```bash
flatpak-builder --user --install --force-clean build-dir io.github.dyslechtchitect.tfcbm.yml
```

### Via GNOME Software

Simply uninstall TFCBM from GNOME Software or App Center.

### Via Command Line

```bash
# Quit the app first (from tray icon menu)
flatpak uninstall io.github.dyslechtchitect.tfcbm

# Remove the GNOME Shell extension
gnome-extensions uninstall tfcbm-clipboard-monitor@github.com
```

## Contributing

Contributions are welcome! Here's how you can help:

- 🐛 **Report bugs**: Open an issue on GitHub
- 💡 **Suggest features**: Start a discussion
- 🔧 **Submit pull requests**: Fix bugs or add features
- 📖 **Improve documentation**: Help others understand TFCBM
- 🌍 **Translate**: Help translate TFCBM to your language

Please read our [Contributing Guidelines](CONTRIBUTING.md) before submitting pull requests.


## Support

- **Issues**: [GitHub Issues](https://github.com/dyslechtchitect/tfcbm/issues)
- **Discussions**: [GitHub Discussions](https://github.com/dyslechtchitect/tfcbm/discussions)
- **Email**: dyslechtchitect@gmail.com

## License

TFCBM is free and open source software licensed under the [GNU General Public License v3.0 or later](LICENSE).

## Acknowledgments

Built with:
- [GTK4](https://www.gtk.org/) - UI toolkit
- [Libadwaita](https://gnome.pages.gitlab.gnome.org/libadwaita/) - GNOME design system
- [Python](https://www.python.org/) - Programming language
- [GNOME Shell](https://www.gnome.org/) - Desktop environment

Special thanks to the GNOME community for creating amazing tools and libraries.

---

<p align="center">Made with ❤️ for the GNOME community</p>
