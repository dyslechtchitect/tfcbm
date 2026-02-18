#!/bin/bash
# AUR Deploy Script for TFCBM
# Run this on Arch Linux to publish or update the AUR package.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AUR_DIR="$SCRIPT_DIR/aur-tfcbm"
PKGVER="1.1.1"

# Allow overriding version: ./aur-deploy.sh 1.2.0
if [ -n "$1" ]; then
  PKGVER="$1"
fi

echo "==> Deploying tfcbm v${PKGVER} to AUR..."

# Clone or update the AUR repo
if [ -d "$AUR_DIR" ]; then
  echo "==> AUR repo already exists, pulling latest..."
  cd "$AUR_DIR"
  git pull
else
  echo "==> Cloning AUR repo..."
  git clone ssh://aur@aur.archlinux.org/tfcbm.git "$AUR_DIR"
  cd "$AUR_DIR"
fi

# Write the PKGBUILD with the target version
cat > PKGBUILD << PKGBUILD_EOF
# Maintainer: dyslechtchitect <your-email@example.com>
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
source=("\${pkgname}-\${pkgver}.tar.gz::https://github.com/dyslechtchitect/tfcbm/archive/refs/tags/v\${pkgver}.tar.gz")
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

echo "==> Generating checksums..."
updpkgsums

echo "==> Generating .SRCINFO..."
makepkg --printsrcinfo > .SRCINFO

echo "==> Committing and pushing..."
git add PKGBUILD .SRCINFO
if git diff --cached --quiet; then
  echo "==> No changes to commit. Already up to date."
else
  git commit -m "Update to ${PKGVER}"
  git push
  echo ""
  echo "==> SUCCESS! Pushed tfcbm v${PKGVER} to AUR."
  echo "    https://aur.archlinux.org/packages/tfcbm"
fi
