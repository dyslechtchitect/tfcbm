#!/bin/bash
# One-script installer and runner for Shortcut Recorder POC
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXTENSION_UUID="shortcut-recorder-poc@example.org"
EXTENSION_DIR="$HOME/.local/share/gnome-shell/extensions/$EXTENSION_UUID"
VENV_DIR="$SCRIPT_DIR/.venv"

cd "$SCRIPT_DIR"

echo "=== Shortcut Recorder POC - Setup & Run ==="
echo ""

# 1. Setup Python virtual environment and dependencies
if [ ! -d "$VENV_DIR" ]; then
    echo "🐍 Creating Python virtual environment..."
    python3 -m venv --system-site-packages "$VENV_DIR"
    echo "✓ Virtual environment created"
fi

echo "🐍 Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# Install/upgrade dependencies
if [ -f "requirements.txt" ]; then
    echo "📦 Installing Python dependencies..."
    pip install --upgrade pip > /dev/null 2>&1
    pip install -r requirements.txt > /dev/null 2>&1
    echo "✓ Dependencies installed"
    echo ""
fi

# 2. Check if extension is installed
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

# 3. Enable extension if not enabled
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

# 4. Make main scripts executable
chmod +x src/main.py 2>/dev/null || chmod +x main.py 2>/dev/null || true

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

# Try new structure first, fall back to old
if [ -f "src/main.py" ]; then
    exec python3 -m src.main
else
    exec ./main.py
fi
