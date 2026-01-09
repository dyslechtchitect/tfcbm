#!/bin/bash
# Script to remove all Meson-installed TFCBM files

set -e

echo "Removing Meson-installed TFCBM files..."

# Remove binaries
echo "Removing binaries..."
sudo rm -vf /usr/local/bin/tfcbm
sudo rm -vf /usr/local/bin/tfcbm-install-extension

# Remove D-Bus service file
echo "Removing D-Bus service file..."
sudo rm -vf /usr/local/share/dbus-1/services/io.github.dyslechtchitect.tfcbm.service

# Remove application files
echo "Removing application files..."
sudo rm -vrf /usr/local/lib/tfcbm
sudo rm -vrf /usr/local/share/tfcbm

# Remove desktop file
echo "Removing desktop file..."
sudo rm -vf /usr/local/share/applications/io.github.dyslechtchitect.tfcbm.desktop

# Remove icon
echo "Removing icon..."
sudo rm -vf /usr/local/share/icons/hicolor/scalable/apps/io.github.dyslechtchitect.tfcbm.svg

# Remove metainfo
echo "Removing metainfo..."
sudo rm -vf /usr/local/share/metainfo/io.github.dyslechtchitect.tfcbm.metainfo.xml

# Update icon cache
echo "Updating icon cache..."
sudo gtk-update-icon-cache /usr/local/share/icons/hicolor/ 2>/dev/null || true

# Update desktop database
echo "Updating desktop database..."
sudo update-desktop-database /usr/local/share/applications/ 2>/dev/null || true

echo ""
echo "✓ All Meson-installed TFCBM files have been removed!"
echo ""
echo "Remaining TFCBM installations:"
which tfcbm 2>/dev/null || echo "  No tfcbm command found in PATH"
flatpak list | grep tfcbm || echo "  No Flatpak installation found"
