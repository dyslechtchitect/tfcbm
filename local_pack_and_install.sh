#!/bin/bash
# Local development build script - builds from local directory instead of git repo

set -e  # Exit on error

MANIFEST="io.github.dyslechtchitect.tfcbm.yml"
LOCAL_MANIFEST="io.github.dyslechtchitect.tfcbm.local.yml"
BUILD_DIR="build-dir"

echo "🔧 Creating local development manifest..."

# Create a temporary manifest that uses local directory
sed 's|type: git|type: dir|g; s|url: .*|path: .|g; s|tag: .*||g' "$MANIFEST" > "$LOCAL_MANIFEST"

echo "📦 Building and installing Flatpak from local sources..."
flatpak-builder --user --install --force-clean "$BUILD_DIR" "$LOCAL_MANIFEST"

echo "✅ Build complete! You can now run: flatpak run io.github.dyslechtchitect.tfcbm"

# Clean up temporary manifest
rm -f "$LOCAL_MANIFEST"
