#!/bin/bash

# TFCBM Unified Setup and Run Script
# This script sets up everything needed and launches TFCBM

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}==>${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Check if running on GNOME
check_gnome() {
    print_status "Checking desktop environment..."
    if [ "$XDG_CURRENT_DESKTOP" != "GNOME" ]; then
        print_error "This application requires GNOME Shell"
        exit 1
    fi
    print_success "GNOME Shell detected"
}

# Install system dependencies
install_system_deps() {
    print_status "Checking system dependencies..."

    # Detect package manager and set package names
    if command -v dnf &>/dev/null; then
        PKG_MANAGER="dnf"
        REQUIRED_PACKAGES="python3 python3-pip python3-gobject gtk4 libadwaita"
    elif command -v apt-get &>/dev/null; then
        PKG_MANAGER="apt-get"
        REQUIRED_PACKAGES="python3 python3-pip python3-venv python3-gi gtk4 libadwaita-1-0"
    else
        print_error "Unsupported package manager. Please install dependencies manually."
        exit 1
    fi

    MISSING_PACKAGES=""

    # Check each package
    for pkg in $REQUIRED_PACKAGES; do
        if [ "$PKG_MANAGER" = "dnf" ]; then
            if ! rpm -q "$pkg" &>/dev/null; then
                MISSING_PACKAGES="$MISSING_PACKAGES $pkg"
            fi
        elif [ "$PKG_MANAGER" = "apt-get" ]; then
            if ! dpkg -l "$pkg" &>/dev/null 2>&1; then
                MISSING_PACKAGES="$MISSING_PACKAGES $pkg"
            fi
        fi
    done

    if [ -n "$MISSING_PACKAGES" ]; then
        print_warning "Missing packages:$MISSING_PACKAGES"
        echo -n "Install missing packages? [y/N] "
        read -r response
        if [[ "$response" =~ ^[Yy]$ ]]; then
            if [ "$PKG_MANAGER" = "dnf" ]; then
                sudo dnf install -y $MISSING_PACKAGES
            elif [ "$PKG_MANAGER" = "apt-get" ]; then
                sudo apt-get install -y $MISSING_PACKAGES
            fi
            print_success "System packages installed"
        else
            print_error "Required packages not installed. Exiting."
            exit 1
        fi
    else
        print_success "All system dependencies satisfied"
    fi
}

# Setup Python virtual environment
setup_venv() {
    print_status "Setting up Python virtual environment..."

    if [ ! -d ".venv" ]; then
        python3 -m venv .venv
        print_success "Virtual environment created"
    else
        print_success "Virtual environment already exists"
    fi

    # Activate and install requirements
    source .venv/bin/activate

    if [ -f "requirements.txt" ]; then
        print_status "Installing Python dependencies..."
        pip install --upgrade pip
        pip install -r requirements.txt
        print_success "Python dependencies installed"
    fi
}

# Compile GSettings schemas
compile_schemas() {
    print_status "Compiling GSettings schemas..."

    SCHEMA_DIR="$SCRIPT_DIR/gnome-extension/schemas"
    if [ -d "$SCHEMA_DIR" ]; then
        glib-compile-schemas "$SCHEMA_DIR"
        print_success "Schemas compiled"
    else
        print_warning "Schema directory not found: $SCHEMA_DIR"
    fi
}

# Install GNOME extension
install_extension() {
    print_status "Installing GNOME Shell extension..."

    EXTENSION_UUID="simple-clipboard@tfcbm"
    EXTENSION_DIR="$HOME/.local/share/gnome-shell/extensions/$EXTENSION_UUID"

    # Remove old installation
    if [ -d "$EXTENSION_DIR" ]; then
        rm -rf "$EXTENSION_DIR"
    fi

    # Create extension directory
    mkdir -p "$EXTENSION_DIR"

    # Copy extension files
    cp -r gnome-extension/* "$EXTENSION_DIR/"

    print_success "Extension installed to $EXTENSION_DIR"
}

# Enable the extension
enable_extension() {
    print_status "Checking extension status..."

    EXTENSION_UUID="simple-clipboard@tfcbm"

    if gnome-extensions list | grep -q "$EXTENSION_UUID"; then
        if gnome-extensions info "$EXTENSION_UUID" | grep -q "State: ENABLED"; then
            print_success "Extension already enabled"
        else
            print_status "Enabling extension..."
            gnome-extensions enable "$EXTENSION_UUID"
            print_success "Extension enabled"
        fi
    else
        print_warning "Extension not found in GNOME Shell"
        echo ""
        print_warning "You may need to log out and log back in for the extension to be recognized."
        echo -n "Log out now? [y/N] "
        read -r response
        if [[ "$response" =~ ^[Yy]$ ]]; then
            gnome-session-quit --logout --no-prompt
            exit 0
        else
            print_status "Please log out and log back in, then run this script again."
            exit 0
        fi
    fi
}

# Start the backend server
start_backend() {
    print_status "Checking backend server..."

    # Check if server is already running
    if pgrep -f "python.*backend.py" > /dev/null; then
        print_success "Backend server already running"
    else
        print_status "Starting backend server..."
        .venv/bin/python3 backend.py > /tmp/tfcbm_backend.log 2>&1 &
        sleep 2
        if pgrep -f "python.*backend.py" > /dev/null; then
            print_success "Backend server started"
        else
            print_warning "Backend server may have failed to start. Check /tmp/tfcbm_backend.log"
            # Don't exit - UI can still work without backend
        fi
    fi
}

# Launch the UI
launch_ui() {
    print_status "Launching TFCBM UI..."

    # Kill any existing UI instances
    pkill -f "python.*ui/main.py" 2>/dev/null || true
    sleep 1

    # Launch UI
    .venv/bin/python3 ui/main.py &

    print_success "TFCBM UI launched!"
    echo ""
    print_status "You can now:"
    echo "  • Press Ctrl+Escape to toggle the UI (or your custom shortcut)"
    echo "  • Click the clipboard icon in the system tray"
    echo "  • Configure shortcuts in Settings"
}

# Main execution
main() {
    echo ""
    echo "=========================================="
    echo "    TFCBM Setup and Launch Script"
    echo "=========================================="
    echo ""

    check_gnome
    install_system_deps
    setup_venv
    compile_schemas
    install_extension
    enable_extension
    start_backend
    launch_ui

    echo ""
    echo "=========================================="
    print_success "Setup complete!"
    echo "=========================================="
    echo ""
}

# Run main function
main
