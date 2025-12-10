#!/usr/bin/env python3
import subprocess
import os

KEYBINDINGS_SCHEMA = "org.gnome.settings-daemon.plugins.media-keys"
KEYBINDINGS_KEY = "custom-keybindings"
CUSTOM_KEYBINDING_SCHEMA = "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DBUS_COMMAND = os.path.join(SCRIPT_DIR, 'activate_app.sh')

def _run_gsettings(args):
    try:
        command = ['gsettings'] + args
        result = subprocess.run(
            command, capture_output=True, text=True, check=True, timeout=2
        )
        return result.stdout.strip().strip("'")
    except Exception as e:
        print(f"Error: {e}")
        return None

print(f"Looking for command: {DBUS_COMMAND}")
list_str = _run_gsettings(['get', KEYBINDINGS_SCHEMA, KEYBINDINGS_KEY])
print(f"Bindings list: {list_str}")

if list_str and list_str != "@as []":
    current_bindings = eval(list_str)
    for path in current_bindings:
        cmd = _run_gsettings(['get', f"{CUSTOM_KEYBINDING_SCHEMA}:{path}", 'command'])
        print(f"  Path: {path}")
        print(f"  Command: {cmd}")
        print(f"  Match: {cmd == DBUS_COMMAND}")
        if cmd == DBUS_COMMAND:
            print(f"  ✓ FOUND!")
