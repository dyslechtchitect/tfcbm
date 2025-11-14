#!/bin/bash
# Robust Uninstallation Script for Simple Clipboard Monitor GNOME Shell Extension

echo "Starting robust uninstallation of Simple Clipboard Monitor Extension..."

EXTENSION_ID="simple-clipboard@tfcbm"
EXTENSION_DIR="$HOME/.local/share/gnome-shell/extensions/$EXTENSION_ID"

# Disable extension (allow failure if not enabled)
echo "Attempting to disable extension '$EXTENSION_ID'..."
set +e # Allow gnome-extensions disable to fail without stopping the script
gnome-extensions disable "$EXTENSION_ID" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Note: Extension '$EXTENSION_ID' was not enabled or already disabled."
else
    echo "✓ Extension '$EXTENSION_ID' disabled."
fi
set -e # Re-enable exit on error for subsequent commands

# Remove extension directory
if [ -d "$EXTENSION_DIR" ]; then
    echo "Removing extension files from '$EXTENSION_DIR'..."
    rm -rf "$EXTENSION_DIR"
    echo "✓ Extension files removed."
else
    echo "Extension directory '$EXTENSION_DIR' not found (already removed or never installed)."
fi

echo ""
echo "Uninstallation complete!"
echo "Note: You may need to restart GNOME Shell to complete removal:"
echo "  - On Wayland: Log out and log back in"
echo "  - On X11: Press Alt+F2, type 'r', press Enter"
echo ""
