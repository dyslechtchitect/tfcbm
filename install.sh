#!/bin/bash
# Install system dependencies for TFCBM

set -e

echo "Installing system dependencies..."
sudo dnf install -y \
    gcc \
    cairo-devel \
    gobject-introspection-devel \
    gtk3-devel \
    pkg-config \
    python3-devel \
    grim

echo ""
echo "Installing Python dependencies..."
pip install -r requirements.txt

echo ""
echo "✓ Installation complete!"
echo ""
echo "grim installed for screenshot capture (Wayland)"
