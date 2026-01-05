#!/bin/bash
export PYTHONPATH="@pkglibdir@:${PYTHONPATH}"
cd @pkglibdir@

# Start the IPC server in background
@PYTHON@ main.py > /tmp/tfcbm_server.log 2>&1 &
SERVER_PID=$!

# Give server a moment to start
sleep 0.5

# Launch the UI with server PID
exec @PYTHON@ ui/main.py --server-pid $SERVER_PID "$@"
