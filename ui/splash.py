#!/usr/bin/env python3
"""
TFCBM Splash Screen - Shows during startup
"""

import random
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk

# Funny loading phrases
LOADING_PHRASES = [
    "Copying your s***...",
    "Initializing the ****ing clipboard...",
    "Loading your copy-paste history...",
    "Preparing to manage the hell out of your clipboard...",
    "Ctrl+C, Ctrl+V... Ctrl+TFCBM!",
    "Warming up the clipboard engines...",
    "Teaching your clipboard some manners...",
    "Dusting off those old copies...",
    "Getting your paste game ready...",
    "Because remembering what you copied is hard...",
    "Clipboard management: Now less * annoying!",
    "Fetching all the things you forgot you copied...",
    "Making clipboard history great again...",
    "Loading all your accidental copies...",
    "Preparing to un**** your clipboard...",
]


class SplashWindow(Gtk.Window):
    """Standalone splash screen window"""

    def __init__(self):
        super().__init__()
        self.set_title("TFCBM")
        self.set_default_size(500, 500)
        self.set_decorated(False)  # Remove window decorations
        self.set_resizable(False)

        # Add rounded corners and shadow via CSS
        self.add_css_class("splash-window")

        # Create main box
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        box.set_halign(Gtk.Align.CENTER)
        box.set_valign(Gtk.Align.CENTER)
        box.set_margin_top(40)
        box.set_margin_bottom(40)
        box.set_margin_start(40)
        box.set_margin_end(40)

        # Try to load TFCBM logo
        try:
            # Try Flatpak path first, then development path
            svg_paths = [
                Path("/app/share/icons/hicolor/scalable/apps/io.github.dyslechtchitect.tfcbm.svg"),
                Path(__file__).parent.parent / "icons" / "hicolor" / "scalable" / "apps" / "io.github.dyslechtchitect.tfcbm.svg"
            ]

            loaded = False
            for svg_path in svg_paths:
                if svg_path.exists():
                    texture = Gdk.Texture.new_from_file(Gio.File.new_for_path(str(svg_path)))
                    logo = Gtk.Picture.new_for_paintable(texture)
                    logo.set_size_request(256, 256)
                    box.append(logo)
                    loaded = True
                    break

            if not loaded:
                print("TFCBM logo not found")
        except Exception as e:
            print(f"Could not load splash logo: {e}")

        # App title
        title = Gtk.Label(label="TFCBM")
        title.add_css_class("title-1")
        box.append(title)

        # Subtitle
        subtitle = Gtk.Label(label="The * Clipboard Manager")
        subtitle.add_css_class("dim-label")
        box.append(subtitle)

        # Loading spinner
        spinner = Gtk.Spinner()
        spinner.set_size_request(48, 48)
        spinner.start()
        box.append(spinner)

        # Loading text with random funny phrase
        loading_phrase = random.choice(LOADING_PHRASES)
        loading_label = Gtk.Label(label=loading_phrase)
        loading_label.add_css_class("title-4")
        loading_label.set_margin_top(10)
        box.append(loading_label)

        # Store label for rotation
        self.loading_label = loading_label

        # Rotate phrases every 2 seconds
        GLib.timeout_add_seconds(2, self._rotate_phrase)

        self.set_child(box)

        # Center the window on screen
        self.set_modal(False)

    def _rotate_phrase(self):
        """Rotate to a new funny phrase"""
        if self.loading_label:
            new_phrase = random.choice(LOADING_PHRASES)
            self.loading_label.set_label(new_phrase)
            return True  # Continue timeout
        return False


class SplashApp(Gtk.Application):
    """Minimal application for splash screen"""

    def __init__(self):
        super().__init__(application_id="org.tfcbm.Splash")
        self.window = None

    def do_activate(self):
        if not self.window:
            self.window = SplashWindow()
            self.window.set_application(self)
            self.window.present()

        # Auto-close after 30 seconds if main UI hasn't started
        GLib.timeout_add_seconds(30, self.quit)


def main():
    """Entry point for splash screen"""
    app = SplashApp()
    return app.run(None)


if __name__ == "__main__":
    sys.exit(main())
