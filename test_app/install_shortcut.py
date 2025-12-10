#!/usr/bin/env python3

"""
Installs a custom keyboard shortcut in GNOME to activate the popup_app
by calling its D-Bus method.

This script modifies GSettings and may require a logout/login for the changes
to be visible in the GNOME Settings UI, but the shortcut should work immediately.
"""

import subprocess
import sys
import os

# --- Configuration ---
# Setting the name to an empty string is a trick to prevent GNOME from showing
# a notification when the shortcut is activated.
# Must use "''" to represent an empty string for gsettings
SHORTCUT_NAME = "''"
# <Primary> is the generic name for Ctrl. This is the new default.
SHORTCUT_BINDING = "<Primary><Shift>R"
# Use absolute path to wrapper script to avoid GNOME notification
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DBUS_COMMAND = os.path.join(SCRIPT_DIR, 'activate_app.sh')

# --- GSettings Details ---
KEYBINDINGS_SCHEMA = "org.gnome.settings-daemon.plugins.media-keys"
KEYBINDINGS_KEY = "custom-keybindings"
CUSTOM_KEYBINDING_SCHEMA = "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding"
CUSTOM_KEYBINDING_PATH_PREFIX = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/"

def run_gsettings(args):
    """Safely runs a gsettings command and returns the output."""
    try:
        command = ['gsettings'] + args
        result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=5)
        return result.stdout.strip()
    except FileNotFoundError:
        print("Error: 'gsettings' command not found. This script requires a GNOME environment.", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"Error executing gsettings with args: {args}", file=sys.stderr)
        print(f"Stderr: {e.stderr.strip()}", file=sys.stderr)
        # Re-raise to be handled by the caller
        raise
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        raise

def parse_gsettings_list(gsettings_output):
    """
    Parses the string representation of a list from gsettings.
    Example input: "['/path/1/', '/path/2/']" or "@as []"
    """
    if not gsettings_output or gsettings_output == "@as []":
        return []
    try:
        # Using eval is generally not recommended, but the list format from gsettings
        # is a well-known, simple case where it is standard practice.
        return eval(gsettings_output)
    except Exception as e:
        print(f"FATAL: Failed to parse gsettings output: {gsettings_output}", file=sys.stderr)
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

def install_shortcut():
    """Installs the GNOME custom keyboard shortcut."""
    print("Reading existing custom keybindings...")
    
    try:
        current_bindings_list = parse_gsettings_list(
            run_gsettings(['get', KEYBINDINGS_SCHEMA, KEYBINDINGS_KEY])
        )
    except subprocess.CalledProcessError:
        print("Could not read current keybindings. Aborting.", file=sys.stderr)
        return

    # To avoid creating duplicates, check if a shortcut with our command already exists.
    for path in current_bindings_list:
        if not path.startswith(CUSTOM_KEYBINDING_PATH_PREFIX):
            continue
        try:
            # gsettings 'get' returns the string enclosed in single quotes
            existing_cmd = run_gsettings(['get', f"{CUSTOM_KEYBINDING_SCHEMA}:{path}", 'command']).strip("'")
            if existing_cmd == DBUS_COMMAND:
                print("Shortcut with the same command already exists. Verifying all settings...")
                # FIX: Also update the name to ensure it's empty, suppressing notifications.
                run_gsettings(['set', f"{CUSTOM_KEYBINDING_SCHEMA}:{path}", 'name', SHORTCUT_NAME])
                run_gsettings(['set', f"{CUSTOM_KEYBINDING_SCHEMA}:{path}", 'binding', SHORTCUT_BINDING])
                print(f"Name and binding have been updated.")
                print("\n--- Success (shortcut already existed and was updated) ---")
                return
        except subprocess.CalledProcessError:
            # This can happen if a path in the list is broken/dangling. Ignore it.
            print(f"Warning: Could not inspect presumably broken keybinding path: {path}")
            continue

    # Find an available slot index (e.g., custom0, custom1, ...)
    new_binding_index = 0
    new_binding_path = ""
    while True:
        path = f"{CUSTOM_KEYBINDING_PATH_PREFIX}custom{new_binding_index}/"
        if path not in current_bindings_list:
            new_binding_path = path
            break
        new_binding_index += 1
        
    print(f"Found available keybinding slot: {new_binding_path}")

    # Add the new keybinding path to the global list
    new_bindings_list = current_bindings_list + [new_binding_path]
    list_as_str = str(new_bindings_list)

    try:
        print("Adding new keybinding to the system list...")
        run_gsettings(['set', KEYBINDINGS_SCHEMA, KEYBINDINGS_KEY, list_as_str])
        
        # Set the properties for the new keybinding path
        print(f"Setting name to: '{SHORTCUT_NAME}'")
        run_gsettings(['set', f"{CUSTOM_KEYBINDING_SCHEMA}:{new_binding_path}", 'name', SHORTCUT_NAME])
        
        print(f"Setting command to: '{DBUS_COMMAND}'")
        run_gsettings(['set', f"{CUSTOM_KEYBINDING_SCHEMA}:{new_binding_path}", 'command', DBUS_COMMAND])

        print(f"Setting binding to: '{SHORTCUT_BINDING}'")
        run_gsettings(['set', f"{CUSTOM_KEYBINDING_SCHEMA}:{new_binding_path}", 'binding', SHORTCUT_BINDING])
    except (subprocess.CalledProcessError, Exception) as e:
        print(f"\nAn error occurred during installation: {e}", file=sys.stderr)
        print("Attempting to clean up...", file=sys.stderr)
        # Revert the list change if something failed
        run_gsettings(['set', KEYBINDINGS_SCHEMA, KEYBINDINGS_KEY, str(current_bindings_list)])
        print("Cleanup finished. Installation failed.", file=sys.stderr)
        return

    print("\n--- Success! ---")
    print(f"Custom shortcut '{SHORTCUT_NAME}' bound to {SHORTCUT_BINDING} has been created.")
    print("The shortcut should work immediately.")
    print("You may need to log out and back in for the change to appear in the GNOME Settings UI.")

if __name__ == "__main__":
    install_shortcut()