#!/bin/bash
# AUR Local Test Script for TFCBM
# Run this on Arch Linux to build and install the package locally.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT

echo "==> Installing build dependencies..."
sudo pacman -S --needed --noconfirm base-devel git python python-gobject gtk4 gdk-pixbuf2 meson xdotool

echo "==> Setting up build directory in $WORK_DIR..."
cd "$WORK_DIR"

# Write the PKGBUILD
cat > PKGBUILD << 'PKGBUILD_EOF'
# Maintainer: dyslechtchitect <your-email@example.com>
pkgname=tfcbm
pkgver=1.1.1
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
source=("${pkgname}-${pkgver}.tar.gz::https://github.com/dyslechtchitect/tfcbm/archive/refs/tags/v${pkgver}.tar.gz")
sha256sums=('SKIP')

build() {
  cd "${pkgname}-${pkgver}"
  meson setup builddir --prefix=/usr
  meson compile -C builddir
}

package() {
  cd "${pkgname}-${pkgver}"
  meson install -C builddir --destdir="${pkgdir}"
}
PKGBUILD_EOF

echo "==> Generating checksums..."
updpkgsums

echo "==> Building and installing package..."
makepkg -si --noconfirm

echo ""
echo "==> SUCCESS! tfcbm is installed."
echo "    Run 'tfcbm --activate' to verify it works."
