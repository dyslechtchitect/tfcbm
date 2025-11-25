#!/bin/bash

set -e

echo "=========================================="
echo "TFCBM Project Loader"
echo "=========================================="

# --- 0. Kill any other instances of this script ---
echo ""
echo "--> Cleaning up old processes..."
CURRENT_PID=$$
OTHER_PIDS=$(pgrep -f "bash.*load.sh" | grep -v "^${CURRENT_PID}$" || true)
if [ -n "$OTHER_PIDS" ]; then
    echo "    Killing other load.sh instances..."
    echo "$OTHER_PIDS" | xargs kill -9 2>/dev/null || true
fi

# Kill any running server instances
if pgrep -f "tfcbm_server.py" > /dev/null; then
    echo "    Killing existing server instances..."
    pkill -9 -f "tfcbm_server.py" 2>/dev/null || true
fi

# Kill any running UI instances
if pgrep -f "ui/main.py" > /dev/null; then
    echo "    Killing existing UI instances..."
    pkill -9 -f "ui/main.py" 2>/dev/null || true
fi

# Wait for ports to be freed
echo "    Waiting for ports to be freed..."
sleep 2

# Double-check port 8765 is free
if lsof -i:8765 > /dev/null 2>&1; then
    echo "    Port 8765 still in use, force killing..."
    lsof -ti:8765 | xargs kill -9 2>/dev/null || true
    sleep 1
fi

# --- 1. Check for Dependencies ---
if ! command -v npm &> /dev/null || ! command -v pip &> /dev/null; then
    echo "WARNING: npm or pip is not installed."
    echo "Please install them using your system's package manager."
    echo "For Fedora: sudo dnf install npm python3-pip"
    echo "For Debian/Ubuntu: sudo apt install npm python3-pip"
fi

# --- 2. Install GNOME Extension Dependencies ---
echo ""
echo "--> Installing GNOME extension dependencies..."
(cd gnome-extension && npm install)

# --- 3. Install GNOME Extension ---
echo ""
echo "--> Installing GNOME Shell extension..."
bash install_extension.sh

# --- 3.5. Install Desktop Launcher ---
echo ""
echo "--> Installing desktop launcher..."
INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESKTOP_FILE="$HOME/.local/share/applications/tfcbm.desktop"
mkdir -p "$HOME/.local/share/applications"

# Create .desktop file
cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Name=TFCBM
Comment=Clipboard Manager - Manage your clipboard history
Exec=$INSTALL_DIR/tfcbm-launcher.sh
Icon=$INSTALL_DIR/resouces/icon-256.png
Terminal=false
Type=Application
Categories=Utility;GTK;
StartupNotify=true
Keywords=clipboard;manager;history;
EOF

# Update desktop database
if command -v update-desktop-database &> /dev/null; then
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
fi

echo "Desktop launcher installed to: $DESKTOP_FILE"
echo "You can now launch TFCBM from Activities (Super key, type 'TFCBM')"
echo "Logs are saved to: /tmp/tfcbm_server.log and /tmp/tfcbm_ui.log"

# --- 4. Create and set up Python Virtual Environment ---
echo ""
echo "--> Setting up Python virtual environment..."
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

echo "Installing Python dependencies..."
.venv/bin/pip install -r requirements.txt

# --- 4.5. Show splash screen early ---
echo ""
echo "--> Starting splash screen..."
.venv/bin/python3 ui/splash.py &
SPLASH_PID=$!
echo "Splash screen started with PID $SPLASH_PID"

# --- 5. Start the Python Server (UNIX socket + WebSocket + Database) ---
echo ""
echo "--> Starting the TFCBM server..."
echo "    - UNIX socket (for GNOME extension)"
echo "    - WebSocket (for UI)"
echo "    - SQLite database"

# Start server and redirect output to log file
.venv/bin/python3 -u tfcbm_server.py > /tmp/tfcbm_server_v2.log 2>&1 &
SERVER_PID=$!
echo "Server started with PID $SERVER_PID"

# Give server a moment to start both servers
sleep 3

# --- 6. Start the UI ---
echo ""
echo "--> Killing any existing UI instances..."
pkill -f "python3 ui/main.py" 2>/dev/null || true
sleep 0.5

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Starting the TFCBM UI..."
echo "Server logs are shown below"
echo "Press Ctrl+C to stop"
echo ""
echo "=========================================="
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "Shutting down..."
    # Kill splash screen if still running
    kill $SPLASH_PID 2>/dev/null || true
    # Kill server
    pkill -P $SERVER_PID 2>/dev/null || true
    kill $SERVER_PID 2>/dev/null || true
    exit 0
}

trap cleanup INT TERM

# Start the UI in the foreground with server PID
.venv/bin/python3 ui/main.py --server-pid $SERVER_PID

# If UI exits, cleanup
cleanup
