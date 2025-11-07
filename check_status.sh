#!/bin/bash
# TFCBM Status Check Script
# Checks the status of the Simple Clipboard Monitor extension and server

set -e

EXTENSION_DIR="$HOME/.local/share/gnome-shell/extensions/simple-clipboard@tfcbm"
SOCKET_PATH="${XDG_RUNTIME_DIR:-/tmp}/simple-clipboard.sock"

echo "=========================================="
echo "TFCBM Status Check"
echo "=========================================="
echo ""

# Check GNOME Shell version
echo "1. GNOME Shell Version:"
gnome-shell --version
echo ""

# Check if extension is installed
echo "2. Extension Installation:"
if [ -d "$EXTENSION_DIR" ]; then
    echo "✓ Extension directory exists: $EXTENSION_DIR"

    # Check required files
    if [ -f "$EXTENSION_DIR/extension.js" ]; then
        echo "  ✓ extension.js found"
    else
        echo "  ✗ extension.js MISSING"
    fi

    if [ -f "$EXTENSION_DIR/metadata.json" ]; then
        echo "  ✓ metadata.json found"
    else
        echo "  ✗ metadata.json MISSING"
    fi

    if [ -d "$EXTENSION_DIR/src" ]; then
        echo "  ✓ src/ directory found"
        # Check key source files
        [ -f "$EXTENSION_DIR/src/ClipboardMonitorService.js" ] && echo "    ✓ ClipboardMonitorService.js" || echo "    ✗ ClipboardMonitorService.js MISSING"
        [ -f "$EXTENSION_DIR/src/PollingScheduler.js" ] && echo "    ✓ PollingScheduler.js" || echo "    ✗ PollingScheduler.js MISSING"
        [ -d "$EXTENSION_DIR/src/adapters" ] && echo "    ✓ adapters/ directory" || echo "    ✗ adapters/ directory MISSING"
        [ -d "$EXTENSION_DIR/src/domain" ] && echo "    ✓ domain/ directory" || echo "    ✗ domain/ directory MISSING"
    else
        echo "  ✗ src/ directory MISSING (this is the problem!)"
    fi
else
    echo "✗ Extension NOT installed at $EXTENSION_DIR"
fi
echo ""

# Check if extension is enabled
echo "3. Extension Status:"
if gnome-extensions list --enabled | grep -q "simple-clipboard@tfcbm"; then
    echo "✓ Extension is ENABLED"
else
    echo "✗ Extension is NOT enabled"
fi
echo ""

# Get detailed extension info
echo "4. Extension Details:"
gnome-extensions info simple-clipboard@tfcbm 2>/dev/null || echo "✗ Extension not found by gnome-extensions"
echo ""

# Check recent extension logs
echo "5. Recent Extension Logs (last 10 lines):"
journalctl -b 0 --user -o cat /usr/bin/gnome-shell 2>/dev/null | grep -i "simple-clipboard" | tail -10 || echo "No extension logs found"
echo ""

# Check if Python server is running
echo "6. Python Server Status:"
if pgrep -f "tfcbm_server.py" > /dev/null; then
    echo "✓ Python server IS running (PID: $(pgrep -f tfcbm_server.py))"
else
    echo "✗ Python server NOT running"
fi
echo ""

# Check if socket exists
echo "7. UNIX Socket Status:"
if [ -S "$SOCKET_PATH" ]; then
    echo "✓ Socket exists at $SOCKET_PATH"
    ls -lh "$SOCKET_PATH"
else
    echo "✗ Socket does NOT exist at $SOCKET_PATH"
    echo "  (Socket is created when Python server starts)"
fi
echo ""

# Summary
echo "=========================================="
echo "Summary:"
echo "=========================================="

EXT_STATE=$(gnome-extensions info simple-clipboard@tfcbm 2>/dev/null | grep "State:" | awk '{print $2}')

if [ "$EXT_STATE" = "ACTIVE" ]; then
    echo "✓ Extension is ACTIVE and working"
elif [ "$EXT_STATE" = "ERROR" ]; then
    echo "✗ Extension is in ERROR state"
    echo ""
    echo "Common fixes:"
    echo "  1. Check if src/ directory exists (section 2 above)"
    echo "  2. Log out and log back in to restart GNOME Shell"
    echo "  3. Run: gnome-extensions disable simple-clipboard@tfcbm && gnome-extensions enable simple-clipboard@tfcbm"
else
    echo "? Extension state unknown: $EXT_STATE"
fi

if ! pgrep -f "tfcbm_server.py" > /dev/null; then
    echo ""
    echo "To start the Python server:"
    echo "  cd ~/Documents/tfcbm && python3 tfcbm_server.py"
fi

echo ""
