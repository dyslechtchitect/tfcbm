#!/bin/bash
# View TFCBM logs in real-time from all three components
# Usage: ./logs.sh

echo "=========================================="
echo "TFCBM Live Logs"
echo "=========================================="
echo "Monitoring:"
echo "  [SERVER] /tmp/tfcbm_server.log"
echo "  [UI]     /tmp/tfcbm_ui.log"
echo "  [EXT]    GNOME Extension (journalctl)"
echo ""
echo "Press Ctrl+C to stop"
echo "=========================================="
echo ""

# Kill any existing log capture processes
pkill -f "journalctl.*simple-clipboard" 2>/dev/null || true

# Start capturing extension logs in background
(journalctl -f --user -t gnome-shell | grep -i "simple-clipboard\|tfcbm" | sed 's/^/[EXT]    /' &)

# Give journalctl a moment to start
sleep 0.5

# Tail the server and UI logs with prefixes
tail -f /tmp/tfcbm_server.log 2>/dev/null | sed 's/^/[SERVER] /' &
tail -f /tmp/tfcbm_ui.log 2>/dev/null | sed 's/^/[UI]     /' &

# Wait for all background processes
wait
