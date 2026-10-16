#!/bin/bash
# Root of the bundle the app is running from: $SNAP under snap, $APPDIR under
# an AppImage (both the runtime and linuxdeploy's AppRun export it), empty for
# a plain system install. Every installed path is relative to it.
APPROOT="${SNAP:-$APPDIR}"

# Fall back to locating the bundle from this script when neither is set, e.g.
# when an AppDir is executed directly rather than through the AppImage runtime.
if [ -z "$APPROOT" ]; then
    SELF_DIR="$(dirname "$(readlink -f "$0")")"
    for candidate in "$SELF_DIR" "$SELF_DIR/../.."; do
        if [ -f "$candidate@pkglibdir@/main.py" ]; then
            APPROOT="$(cd "$candidate" && pwd)"
            # A system install resolves to "/", which needs no prefix at all.
            [ "$APPROOT" = "/" ] && APPROOT=""
            break
        fi
    done
fi

export LD_LIBRARY_PATH="$APPROOT/usr/lib:$APPROOT/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH}"

PKGLIBDIR="${APPROOT}@pkglibdir@"
export PKGLIBDIR

# Snap carries its own python3 on PATH; an AppImage bundles the interpreter
# inside the bundle; a system install uses the one meson was configured with.
if [ -n "$SNAP" ]; then
    PYTHON="python3"
elif [ -n "$APPROOT" ] && [ -x "$APPROOT/usr/bin/python3" ]; then
    PYTHON="$APPROOT/usr/bin/python3"
else
    PYTHON="@PYTHON@"
fi
export PYTHON

export PYTHONPATH="$PKGLIBDIR:${PYTHONPATH}"

# The bundled interpreter finds its own stdlib relative to argv[0], but the
# site-packages that hold the PyGObject bindings are only picked up when the
# bundle layout matches the build host's, so add them explicitly.
if [ -z "$SNAP" ] && [ -n "$APPROOT" ]; then
    for site_dir in "$APPROOT"/usr/lib/python3/dist-packages \
                    "$APPROOT"/usr/lib/python3.*/dist-packages \
                    "$APPROOT"/usr/lib/python3.*/site-packages \
                    "$APPROOT"/usr/local/lib/python3.*/dist-packages \
                    "$APPROOT"/usr/local/lib/python3.*/site-packages; do
        [ -d "$site_dir" ] && export PYTHONPATH="$site_dir:$PYTHONPATH"
    done
    export PATH="$APPROOT/usr/bin:$PATH"
fi

cd "$PKGLIBDIR" || {
    echo "Error: tfcbm is not installed at $PKGLIBDIR" >&2
    exit 1
}

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
exec -a tfcbm-ui "$PYTHON" "$PKGLIBDIR/ui/main.py" --server-pid $SERVER_PID --activate "$@"
