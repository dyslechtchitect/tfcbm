#!/usr/bin/env python3
"""
Quick test for the AboutWindow
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib

from ui.about import AboutWindow

def main():
    app = Gtk.Application(application_id="org.tfcbm.AboutTest")

    def on_activate(app):
        window = AboutWindow()
        window.set_application(app)
        window.present()
        # Auto-close after 3 seconds for testing
        GLib.timeout_add_seconds(3, lambda: (window.close(), app.quit()))

    app.connect("activate", on_activate)
    return app.run(None)

if __name__ == "__main__":
    sys.exit(main())
