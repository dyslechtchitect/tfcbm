#!/usr/bin/env python3
"""
Shortcut Recorder POC - Demonstrates focus-stealing using GApplication Actions
Records keyboard shortcuts and pops up when they're pressed
"""

import sys
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('Gdk', '4.0')

from gi.repository import Gtk, Adw, Gio, GLib, Gdk

APP_ID = "org.example.ShortcutRecorder"
DBUS_NAME = APP_ID
DBUS_PATH = f"/{APP_ID.replace('.', '/')}"


class ShortcutRecorderWindow(Adw.ApplicationWindow):
    """Main window that records and displays keyboard shortcuts"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title("Shortcut Recorder POC")
        self.set_default_size(500, 400)

        # Create main box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        main_box.set_margin_top(20)
        main_box.set_margin_bottom(20)
        main_box.set_margin_start(20)
        main_box.set_margin_end(20)

        # Header
        header = Gtk.Label()
        header.set_markup("<big><b>Keyboard Shortcut Recorder</b></big>")
        main_box.append(header)

        # Instructions
        instructions = Gtk.Label(
            label="Press Ctrl+Shift+K anywhere to toggle this window!\n\n"
                  "This demonstrates focus-stealing using GApplication Actions."
        )
        instructions.set_wrap(True)
        main_box.append(instructions)

        # Shortcut recorder
        shortcut_frame = Gtk.Frame()
        shortcut_frame.set_label("Record New Shortcut")
        shortcut_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        shortcut_box.set_margin_top(10)
        shortcut_box.set_margin_bottom(10)
        shortcut_box.set_margin_start(10)
        shortcut_box.set_margin_end(10)

        # Instructions
        instructions = Gtk.Label(
            label="Click 'Start Recording' and press any key combination"
        )
        shortcut_box.append(instructions)

        # Display recorded shortcut
        self.shortcut_display = Gtk.Label()
        self.update_current_shortcut_display()
        shortcut_box.append(self.shortcut_display)

        # Recording button
        self.record_btn = Gtk.Button(label="Start Recording")
        self.record_btn.connect("clicked", self.on_record_clicked)
        self.record_btn.set_halign(Gtk.Align.CENTER)
        shortcut_box.append(self.record_btn)

        # Status for recording
        self.recording_status = Gtk.Label()
        shortcut_box.append(self.recording_status)

        shortcut_frame.set_child(shortcut_box)
        main_box.append(shortcut_frame)

        # Status label
        self.status_label = Gtk.Label()
        self.status_label.set_markup("<i>Waiting for keyboard shortcut...</i>")
        main_box.append(self.status_label)

        # Activation counter
        self.activation_count = 0
        self.counter_label = Gtk.Label()
        self.update_counter()
        main_box.append(self.counter_label)

        # Close button
        close_btn = Gtk.Button(label="Close Window")
        close_btn.connect("clicked", lambda _: self.close())
        close_btn.set_halign(Gtk.Align.CENTER)
        main_box.append(close_btn)

        self.set_content(main_box)

        # Recording state
        self.recording = False
        self.recorded_shortcut = None

        # Set up key event controller
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self.on_key_pressed)
        self.add_controller(key_controller)

    def on_record_clicked(self, button):
        """Start/stop recording mode"""
        self.recording = not self.recording

        if self.recording:
            self.record_btn.set_label("Stop Recording")
            self.recording_status.set_markup("<i>Press any key combination...</i>")
            self.recorded_shortcut = None
        else:
            self.record_btn.set_label("Start Recording")
            self.recording_status.set_text("")

    def on_key_pressed(self, controller, keyval, keycode, state):
        """Capture key press events"""
        if not self.recording:
            return False

        # Get the key name
        keyname = Gdk.keyval_name(keyval)
        if not keyname:
            return False

        # Build modifier string
        modifiers = []
        if state & Gdk.ModifierType.CONTROL_MASK:
            modifiers.append("<Ctrl>")
        if state & Gdk.ModifierType.SHIFT_MASK:
            modifiers.append("<Shift>")
        if state & Gdk.ModifierType.ALT_MASK:
            modifiers.append("<Alt>")
        if state & Gdk.ModifierType.SUPER_MASK:
            modifiers.append("<Super>")

        # Ignore modifier-only presses
        if keyname in ['Control_L', 'Control_R', 'Shift_L', 'Shift_R',
                       'Alt_L', 'Alt_R', 'Super_L', 'Super_R', 'Meta_L', 'Meta_R']:
            return False

        # Build the shortcut string
        shortcut = "".join(modifiers) + keyname
        self.recorded_shortcut = shortcut

        # Escape for markup display
        shortcut_escaped = shortcut.replace('<', '&lt;').replace('>', '&gt;')

        # Update display
        self.shortcut_display.set_markup(f"<b>Recorded: {shortcut_escaped}</b>")
        self.recording_status.set_markup(
            f"<span color='green'>✓ Recorded: {shortcut_escaped}</span>\n"
            "<i>Applying to extension...</i>"
        )

        # Stop recording
        self.recording = False
        self.record_btn.set_label("Start Recording")

        # Apply the shortcut to the extension
        self.apply_shortcut_to_extension(shortcut)

        return True

    def update_current_shortcut_display(self):
        """Read and display the current shortcut from extension settings"""
        try:
            import subprocess
            import os

            # Add the extension's schemas directory to GSETTINGS_SCHEMA_DIR
            extension_dir = os.path.expanduser('~/.local/share/gnome-shell/extensions/shortcut-recorder-poc@example.org')
            schema_dir = os.path.join(extension_dir, 'schemas')

            env = os.environ.copy()
            if os.path.exists(schema_dir):
                if 'GSETTINGS_SCHEMA_DIR' in env:
                    env['GSETTINGS_SCHEMA_DIR'] = f"{schema_dir}:{env['GSETTINGS_SCHEMA_DIR']}"
                else:
                    env['GSETTINGS_SCHEMA_DIR'] = schema_dir

            result = subprocess.run([
                'gsettings', 'get',
                'org.gnome.shell.extensions.shortcut-recorder-poc',
                'toggle-shortcut-recorder'
            ], capture_output=True, text=True, env=env)

            if result.returncode == 0:
                # Parse the output: ['<Ctrl><Shift>k'] -> <Ctrl><Shift>k
                current = result.stdout.strip().strip("[]'\"")
                # Escape for markup
                current_escaped = current.replace('<', '&lt;').replace('>', '&gt;')
                self.shortcut_display.set_markup(f"<b>Current: {current_escaped}</b>")
            else:
                self.shortcut_display.set_markup("<b>Current: Not configured</b>")
        except Exception as e:
            print(f"Error reading schema: {e}")
            self.shortcut_display.set_markup("<b>Current: &lt;Ctrl&gt;&lt;Shift&gt;K (default)</b>")

    def apply_shortcut_to_extension(self, shortcut):
        """Update the extension's keybinding with the recorded shortcut"""
        try:
            import subprocess
            import os

            # Convert to gsettings format (lowercase)
            gsettings_shortcut = shortcut.lower().replace("ctrl", "Control").replace("alt", "Alt").replace("shift", "Shift").replace("super", "Super")

            # Add the extension's schemas directory to GSETTINGS_SCHEMA_DIR
            extension_dir = os.path.expanduser('~/.local/share/gnome-shell/extensions/shortcut-recorder-poc@example.org')
            schema_dir = os.path.join(extension_dir, 'schemas')

            env = os.environ.copy()
            if os.path.exists(schema_dir):
                if 'GSETTINGS_SCHEMA_DIR' in env:
                    env['GSETTINGS_SCHEMA_DIR'] = f"{schema_dir}:{env['GSETTINGS_SCHEMA_DIR']}"
                else:
                    env['GSETTINGS_SCHEMA_DIR'] = schema_dir

            # Update the extension's GSettings
            result = subprocess.run([
                'gsettings', 'set',
                'org.gnome.shell.extensions.shortcut-recorder-poc',
                'toggle-shortcut-recorder',
                f"['{gsettings_shortcut}']"
            ], capture_output=True, text=True, env=env)

            # Escape for markup
            shortcut_escaped = shortcut.replace('<', '&lt;').replace('>', '&gt;')

            if result.returncode == 0:
                self.recording_status.set_markup(
                    f"<span color='green'>✓ Applied: {shortcut_escaped}</span>\n"
                    "<i>The new shortcut is now active!</i>"
                )
                # Update the display
                self.update_current_shortcut_display()
            else:
                error_msg = result.stderr.replace('<', '&lt;').replace('>', '&gt;')
                self.recording_status.set_markup(
                    f"<span color='orange'>⚠ Recorded: {shortcut_escaped}</span>\n"
                    f"<i>Could not apply to extension: {error_msg}</i>"
                )
        except Exception as e:
            error_escaped = str(e).replace('<', '&lt;').replace('>', '&gt;')
            self.recording_status.set_markup(
                f"<span color='red'>✗ Error applying shortcut: {error_escaped}</span>"
            )

    def update_counter(self):
        """Update the activation counter display"""
        self.counter_label.set_markup(
            f"<b>Times activated via shortcut: {self.activation_count}</b>"
        )

    def on_shortcut_activated(self):
        """Called when the keyboard shortcut is pressed"""
        self.activation_count += 1
        self.update_counter()
        self.status_label.set_markup(
            f"<span color='green'><b>✓ Activated via keyboard shortcut!</b></span>"
        )
        # Reset status after 2 seconds
        GLib.timeout_add_seconds(2, self.reset_status)

    def reset_status(self):
        """Reset status message"""
        self.status_label.set_markup("<i>Waiting for keyboard shortcut...</i>")
        return False  # Don't repeat


class ShortcutRecorderApp(Adw.Application):
    """Application class with GApplication Action support"""

    def __init__(self):
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS
        )
        self.window = None

    def do_startup(self):
        """Set up the application"""
        Adw.Application.do_startup(self)

        # Create the "show-window" action - this is the KEY to focus-stealing
        show_action = Gio.SimpleAction.new("show-window", None)
        show_action.connect("activate", self._on_show_window_action)
        self.add_action(show_action)

        print(f"[POC] Application started - GAction 'show-window' registered")
        print(f"[POC] DBus name: {DBUS_NAME}")
        print(f"[POC] DBus path: {DBUS_PATH}")

    def do_activate(self):
        """Create and present the main window"""
        if not self.window:
            self.window = ShortcutRecorderWindow(application=self)
            print("[POC] Window created")

        self.window.present()
        print("[POC] Window presented")

    def _on_show_window_action(self, action, parameter):
        """
        Handle the show-window GAction
        This is called by the GNOME Shell extension via DBus
        """
        print("[POC] show-window action triggered!")

        if not self.window:
            self.window = ShortcutRecorderWindow(application=self)

        # Toggle window visibility
        if self.window.is_visible():
            print("[POC] Hiding window")
            self.window.set_visible(False)
        else:
            print("[POC] Showing window via GAction")
            self.window.set_visible(True)
            self.window.present()
            # Notify the window that it was activated via shortcut
            self.window.on_shortcut_activated()


def main():
    """Entry point"""
    app = ShortcutRecorderApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
