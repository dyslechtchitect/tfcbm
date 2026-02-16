#!/bin/bash
export LD_LIBRARY_PATH="$SNAP/usr/lib:$SNAP/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH}"

PKGLIBDIR="${SNAP}@pkglibdir@"
export PKGLIBDIR
PYTHON="${SNAP:+python3}"
PYTHON="${PYTHON:-@PYTHON@}"
export PYTHON

export PYTHONPATH="$PKGLIBDIR:${PYTHONPATH}"
cd "$PKGLIBDIR"

# Log directory for server output
LOG_DIR="${XDG_RUNTIME_DIR:-/tmp}"
SERVER_LOG="$LOG_DIR/tfcbm-server.log"

# Kill any leftover tfcbm processes from previous runs
EXISTING_UI=$(pgrep -x tfcbm-ui 2>/dev/null)
EXISTING_AGENT=$(pgrep -x tfcbm-agent 2>/dev/null)
if [ -n "$EXISTING_UI" ]; then
    kill $EXISTING_UI 2>/dev/null
    sleep 0.2
    kill -9 $EXISTING_UI 2>/dev/null
fi
if [ -n "$EXISTING_AGENT" ]; then
    kill $EXISTING_AGENT 2>/dev/null
    sleep 0.2
    kill -9 $EXISTING_AGENT 2>/dev/null
fi

# Check if server is already running by checking for the IPC socket
SOCKET_PATH="${XDG_RUNTIME_DIR:-/tmp}/tfcbm-ipc.sock"
# Always clean up stale socket after killing old processes
rm -f "$SOCKET_PATH"

# Start the IPC server in background
bash -c 'export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp}"; exec -a tfcbm-agent $PYTHON "$PKGLIBDIR/main.py"' >> "$SERVER_LOG" 2>&1 &
SERVER_PID=$!

# Wait for the IPC socket to appear (up to 10 seconds)
WAITED=0
while [ ! -S "$SOCKET_PATH" ] && [ "$WAITED" -lt 20 ]; do
    sleep 0.5
    WAITED=$((WAITED + 1))
done

if [ ! -S "$SOCKET_PATH" ]; then
    echo "Warning: IPC socket did not appear after 10s. Server may have failed to start." >&2
    echo "Check server log: $SERVER_LOG" >&2
fi

# Launch the UI (handles clipboard monitor + shortcut listener in-process)
exec -a tfcbm-ui $PYTHON ui/main.py --server-pid $SERVER_PID --activate "$@"
