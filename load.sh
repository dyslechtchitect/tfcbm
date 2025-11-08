#!/bin/bash

set -e

echo "=========================================="
echo "TFCBM Project Loader"
echo "=========================================="

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
echo "--> Starting the Python server in the background..."
LOG_FILE="tfcbm_server.log"

if pgrep -f "python3 tfcbm_server.py" > /dev/null; then
    echo "Server is already running."
else
    nohup .venv/bin/python3 tfcbm_server.py > "$LOG_FILE" 2>&1 &
    echo "Server started with PID $! and logging to $LOG_FILE"
fi

# --- 6. Final Instructions ---
echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Make sure the GNOME Shell extension is enabled."
echo "   You might need to restart your GNOME Shell (log out and log in)."
echo "2. The Python server is running in the background."
echo "   To see the logs, run: tail -f tfcbm_server.log"
echo "   To check its status, run: pgrep -f tfcbm_server.py"
echo "   To stop it, use: pkill -f tfcbm_server.py"
echo ""
