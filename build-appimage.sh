#!/bin/bash
# AppImage Build Script for TFCBM
# Builds a portable AppImage from the local source tree.
set -e

APP_ID="io.github.dyslechtchitect.tfcbm"
APP_NAME="tfcbm"
VERSION="1.1.5"
ARCH="x86_64"

# Allow overriding version: ./build-appimage.sh 1.2.0
if [ -n "$1" ]; then VERSION="$1"; fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="$SCRIPT_DIR/appimage-build"
APPDIR="$BUILD_DIR/AppDir"

rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# --- Step 0: Install build dependencies ---
echo "==> Installing build dependencies..."
if command -v pacman &>/dev/null; then
  sudo pacman -S --needed --noconfirm base-devel meson python python-gobject gtk4 gdk-pixbuf2 xdotool curl
elif command -v dnf &>/dev/null; then
  sudo dnf install -y meson python3 python3-gobject gtk4-devel gdk-pixbuf2-devel xdotool curl
elif command -v apt &>/dev/null; then
  sudo apt install -y meson python3 python3-gi gir1.2-gtk-4.0 libgtk-4-dev libgdk-pixbuf-2.0-dev xdotool curl
fi

# --- Step 1: Meson build + install into AppDir ---
echo "==> Building with meson..."
meson setup "$BUILD_DIR/builddir" "$SCRIPT_DIR" --prefix=/usr
meson compile -C "$BUILD_DIR/builddir"
DESTDIR="$APPDIR" meson install -C "$BUILD_DIR/builddir"

# --- Step 2: Download linuxdeploy + GTK plugin ---
echo "==> Downloading linuxdeploy tools..."
cd "$BUILD_DIR"
LINUXDEPLOY="linuxdeploy-x86_64.AppImage"
GTK_PLUGIN="linuxdeploy-plugin-gtk.sh"

if [ ! -f "$LINUXDEPLOY" ]; then
  curl -L -o "$LINUXDEPLOY" \
    "https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/$LINUXDEPLOY"
  chmod +x "$LINUXDEPLOY"
fi
if [ ! -f "$GTK_PLUGIN" ]; then
  curl -L -o "$GTK_PLUGIN" \
    "https://raw.githubusercontent.com/linuxdeploy/linuxdeploy-plugin-gtk/master/linuxdeploy-plugin-gtk.sh"
  chmod +x "$GTK_PLUGIN"
fi

# --- Step 3: Bundle Python runtime ---
echo "==> Bundling Python runtime..."
PYTHON_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")

# Copy Python binary
mkdir -p "$APPDIR/usr/bin"
cp "$(which python3)" "$APPDIR/usr/bin/python3"

# Copy standard library
mkdir -p "$APPDIR/usr/lib/python${PYTHON_VER}"
cp -r "/usr/lib/python${PYTHON_VER}/." "$APPDIR/usr/lib/python${PYTHON_VER}/"

# Copy PyGObject bindings
SITE_PACKAGES=$(python3 -c "import site; print(site.getsitepackages()[0])")
mkdir -p "$APPDIR/$SITE_PACKAGES"
for pkg in gi pygtkcompat cairo; do
  if [ -d "$SITE_PACKAGES/$pkg" ]; then
    cp -r "$SITE_PACKAGES/$pkg" "$APPDIR/$SITE_PACKAGES/"
  fi
done
# Copy .so modules for gi (pycairo, etc.)
for so in $(find "$SITE_PACKAGES" -maxdepth 1 -name "*.so" 2>/dev/null); do
  cp "$so" "$APPDIR/$SITE_PACKAGES/"
done

# --- Step 4: Bundle GI typelibs ---
echo "==> Bundling GI typelibs..."
mkdir -p "$APPDIR/usr/lib/girepository-1.0"
TYPELIBS="Gtk-4.0 Gdk-4.0 GdkPixbuf-2.0 Gio-2.0 GLib-2.0 GObject-2.0 \
  Pango-1.0 PangoCairo-1.0 cairo-1.0 Graphene-1.0 GdkX11-4.0 \
  GdkWayland-4.0 Gsk-4.0 HarfBuzz-0.0 freetype2-2.0 Adw-1"

for typelib in $TYPELIBS; do
  for search_dir in /usr/lib/girepository-1.0 /usr/lib/x86_64-linux-gnu/girepository-1.0 /usr/lib64/girepository-1.0; do
    if [ -f "$search_dir/${typelib}.typelib" ]; then
      cp "$search_dir/${typelib}.typelib" "$APPDIR/usr/lib/girepository-1.0/"
      break
    fi
  done
done

# --- Step 5: Bundle xdotool ---
echo "==> Bundling xdotool..."
XDOTOOL_BIN=$(which xdotool 2>/dev/null || true)
if [ -n "$XDOTOOL_BIN" ]; then
  cp "$XDOTOOL_BIN" "$APPDIR/usr/bin/"
else
  echo "WARNING: xdotool not found, auto-paste will not work in the AppImage"
fi

# --- Step 6: Copy GLib schemas ---
echo "==> Bundling GLib schemas..."
mkdir -p "$APPDIR/usr/share/glib-2.0/schemas"
cp /usr/share/glib-2.0/schemas/gschemas.compiled "$APPDIR/usr/share/glib-2.0/schemas/" 2>/dev/null || true

# --- Step 7: Run linuxdeploy ---
echo "==> Running linuxdeploy..."
export DEPLOY_GTK_VERSION=4
./"$LINUXDEPLOY" \
  --appdir "$APPDIR" \
  --desktop-file "$APPDIR/usr/share/applications/${APP_ID}.desktop" \
  --icon-file "$APPDIR/usr/share/icons/hicolor/scalable/apps/${APP_ID}.svg" \
  --plugin gtk \
  --output appimage

# Rename output
OUTPUT="${APP_NAME}-${VERSION}-${ARCH}.AppImage"
mv TFCBM*.AppImage "$OUTPUT" 2>/dev/null || \
mv *.AppImage "$OUTPUT" 2>/dev/null || true

if [ -f "$OUTPUT" ]; then
  mv "$OUTPUT" "$SCRIPT_DIR/$OUTPUT"
  echo ""
  echo "==> SUCCESS! AppImage created: $OUTPUT"
  echo ""
  echo "    To run it:"
  echo "      chmod +x $OUTPUT"
  echo "      ./$OUTPUT"
else
  echo "==> ERROR: AppImage was not created" >&2
  exit 1
fi
