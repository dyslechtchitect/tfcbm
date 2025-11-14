#!/bin/bash
# Test the new TFCBM architecture with SQLite + WebSocket

set -e

echo "=========================================="
echo "TFCBM Architecture Test"
echo "=========================================="

# Kill any existing instances
echo ""
echo "1. Cleaning up existing processes..."
pkill -9 -f tfcbm_server 2>/dev/null || true
pkill -9 -f "python3 ui/main.py" 2>/dev/null || true
rm -f /run/user/1000/simple-clipboard.sock
sleep 1

# Clean database
echo "2. Resetting database..."
rm -rf ~/.local/share/tfcbm/clipboard.db
echo "   Database cleared"

# Start server
echo ""
echo "3. Starting TFCBM server..."
source .venv/bin/activate
python3 tfcbm_server.py &
SERVER_PID=$!
echo "   Server PID: $SERVER_PID"
sleep 4

# Check if server is running
if ! pgrep -f tfcbm_server > /dev/null; then
    echo "✗ Server failed to start!"
    exit 1
fi
echo "   ✓ Server is running"

# Check socket
if [ -S "/run/user/1000/simple-clipboard.sock" ]; then
    echo "   ✓ UNIX socket created"
else
    echo "✗ UNIX socket not found!"
    exit 1
fi

# Add test items to database via UNIX socket
echo ""
echo "4. Adding test clipboard items..."
python3 test_add_items.py
sleep 1

# Check database
echo ""
echo "5. Verifying database..."
python3 -c "
from database import ClipboardDB
db = ClipboardDB()
items = db.get_items(limit=10)
print(f'   ✓ Database has {len(items)} items')
for item in items[:3]:
    content = item['data'][:50] if isinstance(item['data'], bytes) else str(item['data'])[:50]
    print(f'     - [{item[\"id\"]}] {item[\"type\"]}: {content}')
db.close()
"

echo ""
echo "=========================================="
echo "Test Complete!"
echo "=========================================="
echo ""
echo "Server is running (PID: $SERVER_PID)"
echo "  - UNIX socket: /run/user/1000/simple-clipboard.sock"
echo "  - WebSocket: ws://localhost:8765"
echo "  - Database: ~/.local/share/tfcbm/clipboard.db"
echo ""
echo "You can now run the UI:"
echo "  python3 ui/main.py"
echo ""
echo "Or kill the server:"
echo "  kill $SERVER_PID"
echo ""
