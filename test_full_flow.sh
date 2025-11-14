#!/bin/bash
# Test the full TFCBM flow

set -e

echo "=========================================="
echo "TFCBM Full Flow Test"
echo "=========================================="

# Kill any existing instances
echo ""
echo "1. Cleaning up existing processes..."
pkill -9 -f tfcbm_server 2>/dev/null || true
pkill -9 -f "python3 ui/main.py" 2>/dev/null || true
rm -f /run/user/1000/simple-clipboard.sock
sleep 1

# Start server
echo ""
echo "2. Starting server..."
source .venv/bin/activate
python3 tfcbm_server.py &
SERVER_PID=$!
echo "Server PID: $SERVER_PID"
sleep 2

# Check if server is running
if ! pgrep -f tfcbm_server > /dev/null; then
    echo "✗ Server failed to start!"
    exit 1
fi
echo "✓ Server is running"

# Check socket
if [ -S "/run/user/1000/simple-clipboard.sock" ]; then
    echo "✓ Socket created"
else
    echo "✗ Socket not found!"
    exit 1
fi

# Add test items
echo ""
echo "3. Adding test clipboard items..."
python3 test_add_items.py

# Wait a bit
sleep 1

# Test UI connection
echo ""
echo "4. Testing UI connection..."
python3 test_ui_connection.py

echo ""
echo "=========================================="
echo "Test complete!"
echo "=========================================="
echo ""
echo "Server is still running (PID: $SERVER_PID)"
echo "You can now run: python3 ui/main.py"
echo "Or kill the server with: kill $SERVER_PID"
