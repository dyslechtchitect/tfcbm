#!/bin/bash
# TFCBM - Comprehensive Uninstall Script
# Removes all TFCBM components from the system

set -e

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

echo "=========================================="
echo "TFCBM Uninstallation"
echo "=========================================="
echo ""

# Confirm uninstallation
if [ "$1" != "--force" ] && [ "$1" != "-f" ]; then
    echo -e "${YELLOW}This will completely remove TFCBM from your system.${NC}"
    echo -n "Continue? [y/N] "
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        echo "Uninstallation cancelled."
        exit 0
    fi
    echo ""
fi

# Stop running processes
print_status "Stopping TFCBM processes..."
STOPPED=0

# Kill server processes
if pgrep -f "tfcbm_server.py" > /dev/null; then
    pkill -f "tfcbm_server.py" || true
    STOPPED=1
fi

# Kill UI processes
if pgrep -f "ui/main.py" > /dev/null; then
    pkill -f "ui/main.py" || true
    STOPPED=1
fi

# Kill any python processes from this directory
INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if pgrep -f "$INSTALL_DIR.*python" > /dev/null; then
    pkill -f "$INSTALL_DIR.*python" || true
    STOPPED=1
fi

if [ $STOPPED -eq 1 ]; then
    sleep 1
    print_success "TFCBM processes stopped"
else
    print_status "No running TFCBM processes found"
fi

# Disable and uninstall GNOME extension
EXTENSION_UUID="tfcbm-clipboard-monitor@github.com"
EXTENSION_DIR="$HOME/.local/share/gnome-shell/extensions/$EXTENSION_UUID"

if [ -d "$EXTENSION_DIR" ]; then
    print_status "Removing GNOME extension..."

    # Disable extension first
    if gnome-extensions list 2>/dev/null | grep -q "$EXTENSION_UUID"; then
        gnome-extensions disable "$EXTENSION_UUID" 2>/dev/null || true
        print_success "Extension disabled"
    fi

    # Uninstall extension
    if gnome-extensions uninstall "$EXTENSION_UUID" 2>/dev/null; then
        print_success "Extension uninstalled"
    else
        # Fallback: manually remove directory
        rm -rf "$EXTENSION_DIR"
        print_success "Extension directory removed"
    fi
else
    print_status "GNOME extension not found (already removed)"
fi

# Remove desktop files
print_status "Removing desktop launchers..."
REMOVED_DESKTOP=0

if [ -f "$HOME/.local/share/applications/tfcbm.desktop" ]; then
    rm -f "$HOME/.local/share/applications/tfcbm.desktop"
    REMOVED_DESKTOP=1
fi

if [ -f "$HOME/.local/share/applications/org.tfcbm.ClipboardManager.desktop" ]; then
    rm -f "$HOME/.local/share/applications/org.tfcbm.ClipboardManager.desktop"
    REMOVED_DESKTOP=1
fi

if [ $REMOVED_DESKTOP -eq 1 ]; then
    print_success "Desktop launchers removed"
    # Update desktop database
    if command -v update-desktop-database &> /dev/null; then
        update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
    fi
else
    print_status "No desktop launchers found"
fi

# Remove autostart files
print_status "Removing autostart entries..."
REMOVED_AUTOSTART=0

if [ -f "$HOME/.config/autostart/tfcbm.desktop" ]; then
    rm -f "$HOME/.config/autostart/tfcbm.desktop"
    REMOVED_AUTOSTART=1
fi

if [ -f "$HOME/.config/autostart/org.tfcbm.ClipboardManager.desktop" ]; then
    rm -f "$HOME/.config/autostart/org.tfcbm.ClipboardManager.desktop"
    REMOVED_AUTOSTART=1
fi

if [ $REMOVED_AUTOSTART -eq 1 ]; then
    print_success "Autostart entries removed"
else
    print_status "No autostart entries found"
fi

# Clean up dconf settings
print_status "Cleaning up dconf settings..."
if dconf dump /org/gnome/shell/extensions/tfcbm-clipboard-monitor/ 2>/dev/null | grep -q "\["; then
    dconf reset -f /org/gnome/shell/extensions/tfcbm-clipboard-monitor/ 2>/dev/null || true
    print_success "Dconf settings cleared"
else
    print_status "No dconf settings found"
fi

# Clean up gsettings custom keybindings
print_status "Checking for custom keybindings..."
CUSTOM_KEYBINDINGS=$(gsettings get org.gnome.settings-daemon.plugins.media-keys custom-keybindings 2>/dev/null || echo "[]")
if echo "$CUSTOM_KEYBINDINGS" | grep -q "tfcbm"; then
    print_warning "Found TFCBM keybindings - you may want to remove them manually"
    print_warning "Run: gsettings get org.gnome.settings-daemon.plugins.media-keys custom-keybindings"
fi

# Remove log files
print_status "Cleaning up log files..."
LOG_COUNT=0

# Remove all TFCBM-related log files from /tmp
for logfile in /tmp/tfcbm*.log /tmp/tfcbm*.txt /tmp/tfcbm*.md /tmp/*tfcbm*.log /tmp/*tfcbm*.sh; do
    if [ -f "$logfile" ]; then
        rm -f "$logfile"
        ((LOG_COUNT++))
    fi
done

if [ $LOG_COUNT -gt 0 ]; then
    print_success "Removed $LOG_COUNT log/temp files"
else
    print_status "No log files found"
fi

# Optional: Remove Python virtual environment
echo ""
if [ -d "$INSTALL_DIR/.venv" ]; then
    print_warning "Python virtual environment found at: $INSTALL_DIR/.venv"
    echo -n "Remove virtual environment? [y/N] "
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        rm -rf "$INSTALL_DIR/.venv"
        print_success "Virtual environment removed"
    else
        print_status "Keeping virtual environment"
    fi
fi

# Optional: Remove entire project directory
echo ""
print_warning "The project source code is still at: $INSTALL_DIR"
echo -n "Remove entire TFCBM directory? [y/N] "
read -r response
if [[ "$response" =~ ^[Yy]$ ]]; then
    PARENT_DIR="$(dirname "$INSTALL_DIR")"
    cd "$PARENT_DIR"
    rm -rf "$INSTALL_DIR"
    print_success "Project directory removed"
    echo ""
    echo "=========================================="
    print_success "TFCBM completely removed!"
    echo "=========================================="
    echo ""
    print_status "You may want to restart GNOME Shell to complete the cleanup:"
    echo "  Press Alt+F2, type 'r', and press Enter (X11)"
    echo "  Or log out and log back in (Wayland)"
    exit 0
fi

echo ""
echo "=========================================="
print_success "Uninstallation complete!"
echo "=========================================="
echo ""
print_status "The following were removed:"
echo "  ✓ GNOME Shell extension"
echo "  ✓ Desktop launchers"
echo "  ✓ Autostart entries"
echo "  ✓ Running processes"
echo "  ✓ Log files"
echo "  ✓ Configuration settings"
echo ""
print_status "Source code kept at: $INSTALL_DIR"
echo ""
print_status "Recommended: Restart GNOME Shell to complete cleanup:"
echo "  Press Alt+F2, type 'r', and press Enter (X11)"
echo "  Or log out and log back in (Wayland)"
echo ""
