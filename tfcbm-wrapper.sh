#!/bin/bash
export PYTHONPATH="@pkglibdir@:${PYTHONPATH}"
cd @pkglibdir@

# Check if server is already running by checking for the IPC socket
SOCKET_PATH="${XDG_RUNTIME_DIR:-/tmp}/tfcbm-ipc.sock"
if [ -S "$SOCKET_PATH" ]; then
    # Server already running, find its PID
    SERVER_PID=$(pgrep -f "main.py" | head -1)
    if [ -z "$SERVER_PID" ]; then
        # Socket exists but no server - clean up stale socket
        rm -f "$SOCKET_PATH"
        # Start new server
        @PYTHON@ main.py > /dev/null 2>&1 &
        SERVER_PID=$!
        sleep 0.5
    fi
else
    # Start the IPC server in background
    @PYTHON@ main.py > /dev/null 2>&1 &
    SERVER_PID=$!
    sleep 0.5
fi

# Launch the UI with server PID
exec @PYTHON@ ui/main.py --server-pid $SERVER_PID --activate "$@"
