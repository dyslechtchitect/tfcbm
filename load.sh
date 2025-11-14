#!/bin/bash

set -e

echo "=========================================="
echo "TFCBM Project Loader"
echo "=========================================="

# --- 0. Kill any other instances of this script ---
CURRENT_PID=$$
OTHER_PIDS=$(pgrep -f "bash.*load.sh" | grep -v "^${CURRENT_PID}$" || true)
if [ -n "$OTHER_PIDS" ]; then
    echo "Found other instances of load.sh running. Killing them..."
    echo "$OTHER_PIDS" | xargs kill -9 2>/dev/null || true
    sleep 1
fi

# Also kill any running server instances
if pgrep -f "python3 tfcbm_server.py" > /dev/null; then
    echo "Killing existing server instance..."
    pkill -f "python3 tfcbm_server.py"
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

# --- 4. Create and set up Python Virtual Environment ---
echo ""
echo "--> Setting up Python virtual environment..."
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

echo "Installing Python dependencies..."
.venv/bin/pip install -r requirements.txt

# --- 5. Start the Python Server ---
echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Starting the Python server..."
echo "Press Ctrl+C to stop the server"
echo ""
echo "=========================================="
echo ""

# Start the server in the foreground
.venv/bin/python3 tfcbm_server.py
