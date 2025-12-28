#!/bin/bash

# TFCBM GNOME Extension Installation Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== TFCBM GNOME Extension Installer ===${NC}"

# Get the extension UUID from metadata.json
UUID=$(grep -Po '(?<="uuid": ")[^"]*' metadata.json)
if [ -z "$UUID" ]; then
    echo -e "${RED}Error: Could not find UUID in metadata.json${NC}"
    exit 1
fi

echo "Extension UUID: $UUID"

# Define paths
INSTALL_DIR="$HOME/.local/share/gnome-shell/extensions/$UUID"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check if extension is already installed
if [ -d "$INSTALL_DIR" ]; then
    echo -e "${YELLOW}Extension is already installed at: $INSTALL_DIR${NC}"
    read -p "Do you want to reinstall? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Installation cancelled."
        exit 0
    fi
    echo "Removing old installation..."
    rm -rf "$INSTALL_DIR"
fi

# Create installation directory
echo "Creating installation directory..."
mkdir -p "$INSTALL_DIR"

# Copy extension files
echo "Copying extension files..."
cp "$SCRIPT_DIR/extension.js" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/metadata.json" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/tfcbm.svg" "$INSTALL_DIR/"

# Copy src directory
if [ -d "$SCRIPT_DIR/src" ]; then
    echo "Copying src directory..."
    cp -r "$SCRIPT_DIR/src" "$INSTALL_DIR/"
fi

# Copy schemas directory
if [ -d "$SCRIPT_DIR/schemas" ]; then
    echo "Copying schemas directory..."
    cp -r "$SCRIPT_DIR/schemas" "$INSTALL_DIR/"

    # Compile GSettings schema
    echo "Compiling GSettings schema..."
    glib-compile-schemas "$INSTALL_DIR/schemas/"
fi

# Set correct permissions
echo "Setting permissions..."
chmod -R 755 "$INSTALL_DIR"

echo -e "${GREEN}Extension installed successfully!${NC}"
echo
echo "To enable the extension, you can either:"
echo "  1. Use GNOME Extensions app (recommended)"
echo "  2. Run: gnome-extensions enable $UUID"
echo "  3. Use GNOME Tweaks"
echo

# Ask if user wants to enable the extension now
read -p "Do you want to enable the extension now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Enabling extension..."
    gnome-extensions enable "$UUID"

    # Check if running on X11 or Wayland
    if [ "$XDG_SESSION_TYPE" = "x11" ]; then
        echo -e "${YELLOW}You may need to restart GNOME Shell (Alt+F2, then type 'r' and press Enter)${NC}"
    else
        echo -e "${YELLOW}You may need to log out and log back in for changes to take effect${NC}"
    fi
fi

echo -e "${GREEN}Installation complete!${NC}"
