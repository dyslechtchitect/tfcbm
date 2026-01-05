#!/bin/bash
export PYTHONPATH="/app/lib/tfcbm:${PYTHONPATH}"
cd /app/lib/tfcbm

# Start the IPC server in background
python3 main.py > /tmp/tfcbm_server.log 2>&1 &
SERVER_PID=$!

# Give server a moment to start
sleep 0.5

# Launch the UI with server PID
exec python3 ui/main.py --server-pid $SERVER_PID "$@"
