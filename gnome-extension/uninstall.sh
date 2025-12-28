#!/bin/bash

# TFCBM GNOME Extension Uninstallation Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== TFCBM GNOME Extension Uninstaller ===${NC}"

# Get the extension UUID from metadata.json
if [ -f "metadata.json" ]; then
    UUID=$(grep -Po '(?<="uuid": ")[^"]*' metadata.json)
else
    # If metadata.json doesn't exist, try to find the extension UUID directly
    UUID="tfcbm-clipboard-monitor@github.com"
    echo -e "${YELLOW}Warning: metadata.json not found, using default UUID: $UUID${NC}"
fi

if [ -z "$UUID" ]; then
    echo -e "${RED}Error: Could not determine extension UUID${NC}"
    exit 1
fi

echo "Extension UUID: $UUID"

# Define paths
INSTALL_DIR="$HOME/.local/share/gnome-shell/extensions/$UUID"

# Check if extension is installed
if [ ! -d "$INSTALL_DIR" ]; then
    echo -e "${RED}Extension is not installed at: $INSTALL_DIR${NC}"
    exit 1
fi

# Confirm uninstallation
read -p "Are you sure you want to uninstall the TFCBM GNOME Extension? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Uninstallation cancelled."
    exit 0
fi

# Disable extension if enabled
echo "Disabling extension..."
if gnome-extensions list | grep -q "$UUID"; then
    if gnome-extensions info "$UUID" | grep -q "State: ENABLED"; then
        gnome-extensions disable "$UUID" 2>/dev/null || true
        echo "Extension disabled."
    fi
fi

# Remove extension directory
echo "Removing extension files..."
rm -rf "$INSTALL_DIR"

# Clean up any compiled schemas cache
echo "Cleaning up..."
if [ -d "$HOME/.local/share/glib-2.0/schemas" ]; then
    # Recompile schemas without the removed schema
    glib-compile-schemas "$HOME/.local/share/glib-2.0/schemas/" 2>/dev/null || true
fi

echo -e "${GREEN}Extension uninstalled successfully!${NC}"
echo

# Check if running on X11 or Wayland
if [ "$XDG_SESSION_TYPE" = "x11" ]; then
    echo -e "${YELLOW}You may need to restart GNOME Shell (Alt+F2, then type 'r' and press Enter)${NC}"
else
    echo -e "${YELLOW}You may need to log out and log back in for changes to take effect${NC}"
fi

echo -e "${GREEN}Uninstallation complete!${NC}"
