import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib

import sys
import argparse
import os

# --- Application Window Class ---
class TFCBMActivatorWindow(Adw.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_default_size(400, 300)
        self.set_title("TFCBM Activator")

        label = Gtk.Label(label="Hello from TFCBM Activator!")
        self.set_content(label)
        print("TFCBMActivatorWindow created.")

# --- Application Class ---
class TFCBMActivatorApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="org.tfcbm.Activator",
                         flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.window = None
        print("TFCBMActivatorApp initialized.")

    def do_startup(self):
        # This is called once when the application starts up.
        Gtk.Application.do_startup(self)
        print("TFCBMActivatorApp startup.")

    def do_activate(self):
        # This is called when the application is activated (e.g., first launch, or via self.activate()).
        # It ensures the main window is created and presented.
        print("TFCBMActivatorApp do_activate called.")
        if not self.window:
            self.window = TFCBMActivatorWindow(application=self)
        self.window.present()
        print("Window activated and presented.")

    def do_command_line(self, command_line):
        # This is called when the application receives command-line arguments.
        # It's crucial for handling activation requests from external sources like GNOME Shell.
        print(f"TFCBMActivatorApp do_command_line called with arguments: {command_line.get_arguments()}")

        options = command_line.get_arguments()[1:] # Skip the program name itself
        parser = argparse.ArgumentParser(prog="tfcbm_activator.py")
        parser.add_argument("--activate", action="store_true", help="Activate the main window")
        
        try:
            args = parser.parse_args(options)
        except SystemExit:
            # argparse will call sys.exit() on error, which we don't want here.
            # Instead, we'll just activate the app normally.
            print("Error parsing command-line arguments, activating normally.")
            self.activate()
            return 0

        if args.activate:
            print("Received --activate flag. Requesting window activation...")
            # Calling self.activate() will trigger do_activate, which will present the window.
            # Because this activation originates from a command-line call (which GNOME Shell initiates),
            # it bypasses the focus-stealing prevention.
            self.activate()
        else:
            # If no specific flag, just activate normally (e.g., if launched without arguments)
            print("No --activate flag. Activating normally...")
            self.activate()

        return 0 # Indicate success to the system

# --- Main Entry Point ---
def main():
    app = TFCBMActivatorApp()
    # Run the application. sys.argv is passed to allow Gio.Application to parse its own arguments.
    exit_status = app.run(sys.argv)
    print(f"Application exited with status: {exit_status}")
    return exit_status

if __name__ == "__main__":
    sys.exit(main())
