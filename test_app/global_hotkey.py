#!/usr/bin/env python3
"""
Global hotkey listener using python-xlib.
Runs in a background thread and activates the app when the hotkey is pressed.
"""

import sys
import threading
from Xlib import X, XK, display
from Xlib.error import BadAccess
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import GLib

class GlobalHotkeyListener:
    """Listens for global keyboard shortcuts using X11"""

    def __init__(self, callback):
        self.callback = callback
        self.display = None
        self.root = None
        self.thread = None
        self.running = False
        self.current_hotkey = None

    def parse_accelerator(self, accelerator):
        """
        Parse GTK accelerator string like '<Primary><Shift>R' into X11 keysym and modifiers.
        Returns (keysym, modifiers) or (None, None) if invalid.
        """
        # Parse the accelerator string
        parts = accelerator.replace('<', '').replace('>', ' ').split()
        if not parts:
            return None, None

        key_name = parts[-1]
        modifiers = parts[:-1]

        # Convert key name to keysym
        if len(key_name) == 1:
            # Single character
            keysym = XK.string_to_keysym(key_name.lower())
        else:
            # Special key
            keysym = XK.string_to_keysym(key_name)

        if keysym == 0:
            print(f"Warning: Could not convert key '{key_name}' to keysym", file=sys.stderr)
            return None, None

        # Convert modifiers
        mod_mask = 0
        for mod in modifiers:
            mod_lower = mod.lower()
            if mod_lower in ('primary', 'control', 'ctrl'):
                mod_mask |= X.ControlMask
            elif mod_lower == 'shift':
                mod_mask |= X.ShiftMask
            elif mod_lower in ('alt', 'mod1'):
                mod_mask |= X.Mod1Mask
            elif mod_lower in ('super', 'mod4'):
                mod_mask |= X.Mod4Mask

        return keysym, mod_mask

    def grab_key(self, keysym, modifiers):
        """Grab a key combination globally"""
        if not self.display or not self.root:
            return False

        # Convert keysym to keycode
        keycode = self.display.keysym_to_keycode(keysym)
        if keycode == 0:
            print(f"Warning: Could not convert keysym {keysym} to keycode", file=sys.stderr)
            return False

        try:
            # Grab the key with and without numlock/capslock
            # X11 requires grabbing all combinations of lock keys
            for extra_mod in [0, X.LockMask, X.Mod2Mask, X.LockMask | X.Mod2Mask]:
                self.root.grab_key(
                    keycode,
                    modifiers | extra_mod,
                    True,
                    X.GrabModeAsync,
                    X.GrabModeAsync
                )
            self.display.sync()
            return True
        except BadAccess:
            print(f"Warning: Key combination already grabbed by another application", file=sys.stderr)
            return False

    def ungrab_all(self):
        """Ungrab all keys"""
        if self.root:
            self.root.ungrab_key(X.AnyKey, X.AnyModifier)
            if self.display:
                self.display.sync()

    def set_hotkey(self, accelerator):
        """Set the hotkey to listen for"""
        # Ungrab old hotkey
        self.ungrab_all()

        if not accelerator:
            self.current_hotkey = None
            return True

        # Parse new hotkey
        keysym, modifiers = self.parse_accelerator(accelerator)
        if keysym is None:
            print(f"Failed to parse accelerator: {accelerator}", file=sys.stderr)
            return False

        # Grab new hotkey
        success = self.grab_key(keysym, modifiers)
        if success:
            self.current_hotkey = (keysym, modifiers)
            print(f"Successfully grabbed hotkey: {accelerator}", file=sys.stderr)
        return success

    def listen_loop(self):
        """Main event loop for listening to X11 events"""
        print("Hotkey listener thread started", file=sys.stderr)

        while self.running:
            try:
                # Wait for events with timeout
                while self.display.pending_events() > 0:
                    event = self.display.next_event()

                    if event.type == X.KeyPress:
                        # Hotkey was pressed!
                        # Call callback in main GTK thread
                        GLib.idle_add(self.callback)

                # Small sleep to avoid busy-waiting
                import time
                time.sleep(0.01)

            except Exception as e:
                print(f"Error in hotkey listener: {e}", file=sys.stderr)
                import traceback
                traceback.print_exc()

        print("Hotkey listener thread stopped", file=sys.stderr)

    def start(self, accelerator="<Primary><Shift>R"):
        """Start listening for the hotkey"""
        if self.running:
            return

        try:
            # Connect to X display
            self.display = display.Display()
            self.root = self.display.screen().root

            # Select for KeyPress events on root window
            self.root.change_attributes(event_mask=X.KeyPressMask)

            # Set the hotkey
            if not self.set_hotkey(accelerator):
                print("Failed to set hotkey, continuing anyway...", file=sys.stderr)

            # Start listener thread
            self.running = True
            self.thread = threading.Thread(target=self.listen_loop, daemon=True)
            self.thread.start()

        except Exception as e:
            print(f"Failed to start hotkey listener: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()

    def stop(self):
        """Stop listening"""
        self.running = False
        self.ungrab_all()
        if self.thread:
            self.thread.join(timeout=1.0)
        if self.display:
            self.display.close()
            self.display = None
