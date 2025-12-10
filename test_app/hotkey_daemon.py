#!/usr/bin/env python3
"""
Background daemon that listens for keyboard shortcuts and activates the popup app.
This avoids GNOME's custom keybinding notifications entirely.
"""

import subprocess
import sys
import time
import signal

# Monitor for specific key combinations using xinput
# This is a simple POC - production would use python-xlib or similar

def activate_app():
    """Activate the popup app via D-Bus"""
    try:
        subprocess.run([
            'gdbus', 'call', '--session',
            '--dest', 'com.example.PopupApp',
            '--object-path', '/com/example/PopupApp',
            '--method', 'com.example.PopupApp.Activate'
        ], timeout=2)
    except Exception as e:
        print(f"Failed to activate app: {e}", file=sys.stderr)

def main():
    """Main daemon loop"""
    # For POC: monitor using xdotool or similar
    # This is placeholder - would need proper implementation
    print("Hotkey daemon started", file=sys.stderr)

    # Handle graceful shutdown
    def signal_handler(sig, frame):
        print("Hotkey daemon stopping", file=sys.stderr)
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Keep daemon running
    while True:
        time.sleep(1)

if __name__ == '__main__':
    main()
