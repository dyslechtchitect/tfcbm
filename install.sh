#!/bin/bash
# Install system dependencies for TFCBM

set -e

echo "=========================================="
echo "TFCBM Project Installer"
echo "=========================================="

echo ""
echo "--> Installing system dependencies..."
sudo dnf install -y \
    gcc \
    cairo-devel \
    gobject-introspection-devel \
    gtk3-devel \
    pkg-config \
    python3-devel \
    grim \
    npm

echo ""
echo "--> Installing Python dependencies..."
pip install -r requirements.txt

echo ""
echo "--> Installing GNOME Shell extension..."
bash install_extension.sh

echo ""
echo "=========================================="
echo "✓ Installation complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Restart your GNOME Shell (log out and log in)."
echo "2. Run the server: python3 tfcbm_server.py"
echo ""
