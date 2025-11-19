#!/bin/bash
# TFCBM Launcher - Starts server if needed, then launches UI
# Logs are saved to /tmp/tfcbm_*.log

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Create/truncate log files
: > /tmp/tfcbm_server.log
: > /tmp/tfcbm_ui.log

# Check if server is already running
if ! pgrep -f "tfcbm_server.py" > /dev/null; then
    # Start the server in the background, logging to /tmp/tfcbm_server.log
    .venv/bin/python3 -u tfcbm_server.py >> /tmp/tfcbm_server.log 2>&1 &

    # Wait for server to initialize
    sleep 2
fi

# Launch the UI, logging to /tmp/tfcbm_ui.log
exec .venv/bin/python3 ui/main.py >> /tmp/tfcbm_ui.log 2>&1
