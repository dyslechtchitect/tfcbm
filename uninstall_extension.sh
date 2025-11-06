#!/bin/bash
# Uninstall Simple Clipboard Monitor GNOME Shell Extension

set -e

EXTENSION_DIR="$HOME/.local/share/gnome-shell/extensions/simple-clipboard@tfcbm"

echo "Uninstalling Simple Clipboard Monitor Extension..."

# Disable extension
echo "Disabling extension..."
gnome-extensions disable simple-clipboard@tfcbm 2>/dev/null || echo "Extension was not enabled or already disabled"

# Remove extension directory
if [ -d "$EXTENSION_DIR" ]; then
    echo "Removing extension files from $EXTENSION_DIR..."
    rm -rf "$EXTENSION_DIR"
    echo "✓ Extension files removed"
else
    echo "Extension directory not found (already removed?)"
fi

echo ""
echo "Uninstallation complete!"
echo ""
echo "Note: You may need to restart GNOME Shell to complete removal:"
echo "  - On Wayland: Log out and log back in"
echo "  - On X11: Press Alt+F2, type 'r', press Enter"
echo ""
