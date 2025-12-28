
<h1 align="center">
  <strong>TFCBM - The * Clipboard Manager</strong>
</h1>

<p align="center">
  <img src="resouces/io.github.dyslechtchitect.TFCBM.logo.png" alt="TFCBM Logo" width="36" height="36">
</p>

<p align="center">
  <strong>A powerful, lightweight clipboard manager for GNOME</strong>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-GPL--3.0-blue.svg" alt="License"></a>
  <img src="https://img.shields.io/badge/GNOME-45--49-blue.svg" alt="GNOME 45-49">
  <img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+">
  <a href="https://github.com/dyslechtchitect/tfcbm/actions/workflows/flatpak-ci.yml"><img src="https://github.com/dyslechtchitect/tfcbm/actions/workflows/flatpak-ci.yml/badge.svg" alt="CI Status"></a>
</p>

## Features

- **📋 Complete Clipboard History** - Never lose copied content again
- **🔍 Powerful Search** - Find anything in your clipboard history instantly
- **🏷️ Tags & Organization** - Organize clips with custom tags and colors
- **🖼️ Rich Media Support** - Images, files, URLs, and formatted text
- **🔒 Secret Management** - Mark sensitive items as secrets with password protection
- **⌨️ Keyboard Navigation** - Fast workflow with keyboard shortcuts
- **🎨 Modern UI** - Beautiful Adwaita-based interface
- **🔄 Real-time Sync** - Instant clipboard monitoring via GNOME extension
- **💾 Persistent Storage** - SQLite database with automatic retention management

## Installation

### From Flathub (Recommended)

```bash
flatpak install flathub io.github.dyslechtchitect.TFCBM
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
   flatpak-builder --user --install --force-clean build-dir io.github.dyslechtchitect.TFCBM.yml
   ```

4. Run:
   ```bash
   flatpak run io.github.dyslechtchitect.TFCBM
   ```

## Usage

### First Run

On first launch, TFCBM will install and enable the GNOME Shell extension for clipboard monitoring.

The extension provides:
- System tray icon for quick access
- Real-time clipboard monitoring
- Global keyboard shortcut (`Super+V`)

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Super+V` | Toggle TFCBM window |
| `Ctrl+F` | Focus search |
| `Enter` | Paste selected item and close |
| `Shift+Enter` | Paste selected item (keep window open) |
| `Delete` | Delete selected item |
| `↑/↓` | Navigate clipboard history |
| `Esc` | Close window |

### Tray Icon Menu

- **TFCBM Settings**: Open settings page
- **Quit TFCBM App**: Quit application and disable extension

## Architecture

TFCBM consists of three components:

1. **UI Application** - GTK4/Adwaita frontend
2. **Backend Server** - WebSocket server with SQLite database
3. **GNOME Extension** - Clipboard monitoring and tray integration

## Development

### Prerequisites

- Python 3.11+
- GNOME 45-49
- Flatpak SDK (for packaging)

### Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run server
python3 main.py

# Run UI (in another terminal)
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

### CI/CD

The project uses GitHub Actions for continuous integration:
- Tests run on every push and PR
- Flatpak builds tested against GNOME 45-49
- Artifacts uploaded for each GNOME version

**Run CI locally:**
```bash
# Run tests
./run-ci-locally.sh test

# Build Flatpak for GNOME 49
./run-ci-locally.sh flatpak 49

# Build for all versions
./run-ci-locally.sh flatpak-all
```

See [.github/workflows/LOCAL_TESTING.md](.github/workflows/LOCAL_TESTING.md) for details.

## Configuration

- Clipboard database: `~/.local/share/tfcbm/clipboard.db`
- Extension settings: `dconf /org/gnome/shell/extensions/tfcbm-clipboard-monitor/`

## Uninstalling

1. Click "Quit TFCBM App" from the tray icon
2. Uninstall from GNOME Software

Or via command line:
```bash
flatpak uninstall io.github.dyslechtchitect.TFCBM
gnome-extensions uninstall tfcbm-clipboard-monitor@github.com
```

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes with clear commit messages
4. Add tests for new functionality
5. Submit a pull request

## License

TFCBM is licensed under the GNU General Public License v3.0 or later.
See [LICENSE](LICENSE) for details.

## Support

- **Issues**: [GitHub Issues](https://github.com/dyslechtchitect/tfcbm/issues)
- **Discussions**: [GitHub Discussions](https://github.com/dyslechtchitect/tfcbm/discussions)

---

<p align="center">Made with ❤️ for the GNOME community</p>
