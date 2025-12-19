#!/bin/bash
# One-script installer and runner for Shortcut Recorder POC
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXTENSION_UUID="shortcut-recorder-poc@example.org"
EXTENSION_DIR="$HOME/.local/share/gnome-shell/extensions/$EXTENSION_UUID"

cd "$SCRIPT_DIR"

echo "=== Shortcut Recorder POC - Setup & Run ==="
echo ""

# 1. Check if extension is installed
if [ ! -d "$EXTENSION_DIR" ]; then
    echo "📦 Installing GNOME Shell extension..."
    mkdir -p "$EXTENSION_DIR"
    cp -r gnome-extension/* "$EXTENSION_DIR/"

    echo "🔧 Compiling GSettings schema..."
    glib-compile-schemas "$EXTENSION_DIR/schemas/"

    echo "✓ Extension installed"
    echo ""
    echo "⚠️  GNOME Shell restart required!"
    echo "   → On Wayland: Log out and log back in"
    echo "   → On X11: Press Alt+F2, type 'r', press Enter"
    echo ""
    read -p "Press Enter after restarting GNOME Shell to continue..."
fi

# 2. Enable extension if not enabled
if ! gnome-extensions list --enabled 2>/dev/null | grep -q "$EXTENSION_UUID"; then
    echo "🔌 Enabling extension..."
    if gnome-extensions enable "$EXTENSION_UUID" 2>/dev/null; then
        echo "✓ Extension enabled"
    else
        echo "⚠️  Extension exists but couldn't enable - you may need to restart GNOME Shell first"
        echo "   After restart, run this script again or manually enable:"
        echo "   gnome-extensions enable $EXTENSION_UUID"
    fi
    echo ""
fi

# 3. Check if venv is needed (if requirements.txt or .venv exists in parent)
if [ -f "../.venv/bin/activate" ]; then
    echo "🐍 Activating Python virtual environment..."
    source ../.venv/bin/activate
    echo "✓ Venv activated"
    echo ""
fi

# 4. Make main.py executable
chmod +x main.py

# 5. Kill any existing instance
if pgrep -f "org.example.ShortcutRecorder" > /dev/null 2>&1; then
    echo "🔄 Stopping existing instance..."
    pkill -f "org.example.ShortcutRecorder"
    sleep 1
fi

# 6. Run the application
echo "🚀 Starting Shortcut Recorder POC..."
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Default shortcut: Ctrl+Shift+K"
echo "  Click 'Start Recording' to record a new shortcut"
echo "  Press Ctrl+C here to stop the application"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

exec ./main.py
