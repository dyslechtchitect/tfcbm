#!/bin/bash
# Test if TFCBM extension is running on Ubuntu

echo "=== TFCBM Extension Quick Test ==="
echo ""

echo "1. Check if extension is enabled:"
gnome-extensions info tfcbm-clipboard-monitor@github.com 2>&1 | grep -E "State:|ERROR"
echo ""

echo "2. Watch GNOME Shell logs for TFCBM (press Ctrl+C to stop):"
echo "   Copy something to clipboard while watching..."
echo ""
journalctl -f /usr/bin/gnome-shell | grep --line-buffered TFCBM
