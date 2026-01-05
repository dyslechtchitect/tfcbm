#!/bin/bash
set -e

EXTENSION_UUID="tfcbm-clipboard-monitor@github.com"
EXTENSION_ZIP="/app/share/tfcbm/${EXTENSION_UUID}.zip"

# Detect if we're running inside flatpak
if [ -n "${FLATPAK_ID}" ]; then
    # Running inside flatpak - use flatpak-spawn to run host commands
    CMD_PREFIX="flatpak-spawn --host"
else
    # Running on host
    CMD_PREFIX=""
fi

# Check if gnome-extensions command is available on host
if ! ${CMD_PREFIX} gnome-extensions --version &> /dev/null; then
    echo "Error: gnome-extensions command not found on the host. Are you running GNOME?"
    exit 1
fi

# Check if extension is already installed
if ${CMD_PREFIX} gnome-extensions list 2>/dev/null | grep -q "^${EXTENSION_UUID}$"; then
    echo "Extension ${EXTENSION_UUID} is already installed."
    read -p "Do you want to reinstall? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Installation cancelled."
        exit 0
    fi

    # Uninstall the existing extension
    echo "Uninstalling existing extension..."
    ${CMD_PREFIX} gnome-extensions uninstall "${EXTENSION_UUID}" || true
fi

echo "Installing GNOME Shell extension..."

# Use gnome-extensions install with --force to install/reinstall
if ${CMD_PREFIX} gnome-extensions install --force "${EXTENSION_ZIP}"; then
    echo ""
    echo "✓ Extension installed successfully!"
    echo ""
    echo "Next steps:"
    if [ "$XDG_SESSION_TYPE" = "x11" ]; then
        echo "  1. Restart GNOME Shell: Press Alt+F2, type 'r', and press Enter"
        echo "  2. Enable the extension:"
        echo "     gnome-extensions enable ${EXTENSION_UUID}"
        echo "  3. Launch TFCBM"
    else
        echo "  1. Log out and log back in (required on Wayland)"
        echo "  2. The extension will be automatically enabled"
        echo "  3. Launch TFCBM"
    fi
    echo ""

    # Try to enable it anyway (will work after session restart)
    ${CMD_PREFIX} gnome-extensions enable "${EXTENSION_UUID}" 2>/dev/null || true
else
    echo "Error: Failed to install extension."
    exit 1
fi
