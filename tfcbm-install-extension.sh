#!/bin/bash
set -e

EXTENSION_UUID="tfcbm-clipboard-monitor@github.com"

# If running inside Flatpak, use flatpak-spawn to install on host
if [ -n "${FLATPAK_ID}" ]; then
    echo "Installing TFCBM GNOME Shell Extension..."
    echo ""

    # Create extension directory on host
    flatpak-spawn --host mkdir -p ~/.local/share/gnome-shell/extensions/${EXTENSION_UUID}

    # Copy extension files from Flatpak to host
    # The extension files are bundled at /app/share/gnome-shell/extensions/
    cp -r /app/share/gnome-shell/extensions/${EXTENSION_UUID}/* ~/.local/share/gnome-shell/extensions/${EXTENSION_UUID}/

    echo "✓ Extension files installed"
    echo ""
    echo "Compiling GSettings schema..."

    # Compile the schema (CRITICAL - required for keybindings to work)
    flatpak-spawn --host glib-compile-schemas ~/.local/share/gnome-shell/extensions/${EXTENSION_UUID}/schemas/

    echo "✓ Schema compiled"
    echo ""
    echo "Now enabling the extension..."

    # Enable the extension on the host
    flatpak-spawn --host gnome-extensions enable ${EXTENSION_UUID}

    echo "✓ Extension enabled"
    echo ""
    echo "Installation complete!"
    echo ""
    echo "Note: You may need to restart GNOME Shell for the extension to activate:"
    echo "  - On X11: Press Alt+F2, type 'r', and press Enter"
    echo "  - On Wayland: Log out and log back in"

    exit 0
fi

# Running on host (non-Flatpak)
echo "Running native GNOME extension installer..."
# Execute the install.sh script located in the gnome-extension subdirectory
# We need to change to that directory first for relative paths in install.sh to work
(cd gnome-extension && ./install.sh)
exit 0 # Exit after running native installer

