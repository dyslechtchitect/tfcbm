#!/bin/bash
# Install GNOME Shell extension for Popup App

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXTENSION_DIR="$SCRIPT_DIR/gnome-extension"
INSTALL_DIR="$HOME/.local/share/gnome-shell/extensions/popup-app-hotkey@example.com"

echo "Installing Popup App Hotkey extension..."

# Compile schemas
echo "Compiling GSettings schemas..."
cd "$EXTENSION_DIR/schemas"
glib-compile-schemas .

# Create symlink
echo "Installing extension to $INSTALL_DIR..."
mkdir -p "$(dirname "$INSTALL_DIR")"
ln -sf "$EXTENSION_DIR" "$INSTALL_DIR"

# Try to enable the extension
echo "Enabling extension..."
gnome-extensions enable popup-app-hotkey@example.com 2>/dev/null || {
    echo ""
    echo "====================================="
    echo "Extension installed successfully!"
    echo "====================================="
    echo ""
    echo "To enable the extension, please:"
    echo "1. Log out and log back in"
    echo "   OR"
    echo "2. Press Alt+F2, type 'r', press Enter (to restart GNOME Shell)"
    echo "   OR"
    echo "3. Open Extensions app and toggle 'Popup App Hotkey' ON"
    echo ""
    exit 0
}

echo ""
echo "====================================="
echo "Extension installed and enabled!"
echo "====================================="
echo ""
echo "You may need to restart GNOME Shell for it to take effect:"
echo "• Press Alt+F2, type 'r', press Enter"
