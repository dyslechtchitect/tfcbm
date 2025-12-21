#!/bin/bash
# TFCBM - Installation and Launcher Script
# Usage: ./install.sh          (install/setup)
#        ./install.sh run      (run the app)

set -e

INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$INSTALL_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() { echo -e "${BLUE}==>${NC} $1"; }
print_success() { echo -e "${GREEN}✓${NC} $1"; }
print_error() { echo -e "${RED}✗${NC} $1"; }
print_warning() { echo -e "${YELLOW}⚠${NC} $1"; }

# RUN MODE - Launch the app
if [ "$1" = "run" ]; then
    # Create/truncate log files
    : > /tmp/tfcbm_server.log
    : > /tmp/tfcbm_ui.log

    # Check if server is already running
    if ! pgrep -f "tfcbm_server.py" > /dev/null; then
        # Start the server in the background
        .venv/bin/python3 -u tfcbm_server.py >> /tmp/tfcbm_server.log 2>&1 &
        sleep 2
    fi

    # Launch the UI
    exec .venv/bin/python3 ui/main.py >> /tmp/tfcbm_ui.log 2>&1
fi

# INSTALL MODE - Default
echo "=========================================="
echo "TFCBM Installation"
echo "=========================================="

# Check GNOME
print_status "Checking desktop environment..."
if [ "$XDG_CURRENT_DESKTOP" != "GNOME" ]; then
    print_error "This application requires GNOME Shell"
    exit 1
fi
print_success "GNOME Shell detected"

# Check and install xdotool for auto-paste feature
if ! command -v xdotool &> /dev/null; then
    print_warning "xdotool not found (needed for auto-paste feature)"
    echo -n "Install xdotool? [y/N] "
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        if command -v dnf &> /dev/null; then
            sudo dnf install -y xdotool
        elif command -v apt &> /dev/null; then
            sudo apt install -y xdotool
        fi
    fi
fi

# Setup Python virtual environment
print_status "Setting up Python virtual environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    print_success "Virtual environment created"
fi

source .venv/bin/activate
print_status "Installing Python dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
print_success "Python dependencies installed"

# Create desktop launcher
print_status "Creating desktop launcher..."
DESKTOP_FILE="$HOME/.local/share/applications/tfcbm.desktop"
mkdir -p "$HOME/.local/share/applications"

cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Name=TFCBM
Comment=Clipboard Manager
Exec=$INSTALL_DIR/install.sh run
Icon=$INSTALL_DIR/resouces/icon-256.png
Terminal=false
Type=Application
Categories=Utility;GTK;
StartupNotify=true
Keywords=clipboard;manager;history;
EOF

# Create autostart entry
AUTOSTART_DIR="$HOME/.config/autostart"
AUTOSTART_FILE="$AUTOSTART_DIR/tfcbm.desktop"
mkdir -p "$AUTOSTART_DIR"

cat > "$AUTOSTART_FILE" << EOF
[Desktop Entry]
Type=Application
Name=TFCBM
Exec=$INSTALL_DIR/install.sh run
Icon=$INSTALL_DIR/resouces/icon-256.png
Terminal=false
X-GNOME-Autostart-enabled=true
EOF

print_success "Desktop launcher created"

# Update desktop database
if command -v update-desktop-database &> /dev/null; then
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
fi

echo ""
echo "=========================================="
print_success "Installation complete!"
echo "=========================================="
echo ""
echo "TFCBM has been installed!"
echo ""
echo "NOTE: Make sure you have the GNOME Shell extension installed separately."
echo ""
echo "To start TFCBM:"
echo "  1. Run: $INSTALL_DIR/install.sh run"
echo "  2. Or search for 'TFCBM' in Activities"
echo ""
echo "The app will auto-start on next login."
echo ""
echo "Logs are saved to:"
echo "  - /tmp/tfcbm_server.log"
echo "  - /tmp/tfcbm_ui.log"
echo ""

# Ask if user wants to start now
echo -n "Start TFCBM now? [Y/n] "
read -r response
if [[ ! "$response" =~ ^[Nn]$ ]]; then
    print_status "Starting TFCBM..."
    "$INSTALL_DIR/install.sh" run &
    sleep 2
    print_success "TFCBM is running!"
    echo ""
    echo "Use your keyboard shortcut to toggle the window"
    echo "(Configure in the GNOME extension settings)"
fi
