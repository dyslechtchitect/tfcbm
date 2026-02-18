#!/bin/bash
# AUR Local Test Script for TFCBM
# Builds and installs from the LOCAL git checkout (not a GitHub release tag).
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT

echo "==> Installing build dependencies..."
sudo pacman -S --needed --noconfirm base-devel git pacman-contrib python python-gobject gtk4 gdk-pixbuf2 meson xdotool

# Get maintainer email
read -rp "Enter your maintainer email for PKGBUILD: " MAINTAINER_EMAIL

# Create a tarball from the local checkout
PKGVER="$(git -C "$SCRIPT_DIR" describe --tags --abbrev=0 2>/dev/null | sed 's/^v//' || echo "0.0.0").local"
echo "==> Creating tarball from local checkout (version: $PKGVER)..."
git -C "$SCRIPT_DIR" archive --format=tar.gz --prefix="tfcbm-${PKGVER}/" HEAD > "$WORK_DIR/tfcbm-${PKGVER}.tar.gz"

echo "==> Setting up build directory in $WORK_DIR..."
cd "$WORK_DIR"

# Write the PKGBUILD
cat > PKGBUILD << PKGBUILD_EOF
# Maintainer: dyslechtchitect <${MAINTAINER_EMAIL}>
pkgname=tfcbm
pkgver=${PKGVER}
pkgrel=1
pkgdesc="The Friendly Clipboard Manager - Track and manage your clipboard history"
arch=('any')
url="https://github.com/dyslechtchitect/tfcbm"
license=('GPL-3.0-or-later')
depends=(
  'python'
  'python-gobject'
  'gtk4'
  'gdk-pixbuf2'
  'meson'
  'xdotool'
)
optdepends=(
  'libadwaita: adaptive GNOME styling'
  'webkit2gtk-6.0: HTML preview in clipboard items'
)
source=("tfcbm-\${pkgver}.tar.gz")
sha256sums=('SKIP')

build() {
  cd "\${pkgname}-\${pkgver}"
  meson setup builddir --prefix=/usr
  meson compile -C builddir
}

package() {
  cd "\${pkgname}-\${pkgver}"
  meson install -C builddir --destdir="\${pkgdir}"
}
PKGBUILD_EOF

echo "==> Building and installing package..."
makepkg -si --noconfirm

echo ""
echo "==> SUCCESS! tfcbm (local build) is installed."
echo "    Run 'tfcbm --activate' to verify it works."
