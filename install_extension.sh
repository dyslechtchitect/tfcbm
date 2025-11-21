#!/bin/bash
# Install Simple Clipboard Monitor GNOME Shell Extension

set -e

echo "Installing Simple Clipboard Monitor Extension..."

# Install npm dependencies
echo "--> Installing npm dependencies..."
(cd gnome-extension && npm install)

EXTENSION_DIR="$HOME/.local/share/gnome-shell/extensions/simple-clipboard@tfcbm"

# Create extension directory
mkdir -p "$EXTENSION_DIR"

# Copy files
cp gnome-extension/extension.js "$EXTENSION_DIR/"
cp gnome-extension/metadata.json "$EXTENSION_DIR/"
cp -r gnome-extension/src "$EXTENSION_DIR/"
cp -r gnome-extension/node_modules "$EXTENSION_DIR/"
cp -r gnome-extension/schemas "$EXTENSION_DIR/"

echo "✓ Files copied to $EXTENSION_DIR"

# Enable extension
gnome-extensions enable simple-clipboard@tfcbm 2>/dev/null || echo "Note: You may need to restart GNOME Shell to enable the extension"

echo ""
echo "Installation complete!"
echo ""
echo "Next steps:"
echo "1. Restart GNOME Shell:"
echo "   - On Wayland: Log out and log back in"
echo "   - On X11: Press Alt+F2, type 'r', press Enter"
echo ""
echo "2. Verify extension is enabled:"
echo "   gnome-extensions list --enabled | grep simple-clipboard"
echo ""
echo "3. Start the Python server:"
echo "   python3 tfcbm_server.py"
echo ""
echo "4. Copy some text to test!"
