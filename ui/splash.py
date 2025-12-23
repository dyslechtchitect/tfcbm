#!/usr/bin/env python3
"""
TFCBM Splash Screen - Shows during startup
"""

import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk


class SplashWindow(Gtk.Window):
    """Standalone splash screen window"""

    def __init__(self):
        super().__init__()
        self.set_title("TFCBM")
        self.set_default_size(400, 400)
        self.set_decorated(False)  # Remove window decorations
        self.set_resizable(False)

        # Create main box
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        box.set_halign(Gtk.Align.CENTER)
        box.set_valign(Gtk.Align.CENTER)
        box.set_margin_top(40)
        box.set_margin_bottom(40)
        box.set_margin_start(40)
        box.set_margin_end(40)

        # Try to load TFCBM logo (try SVG first, then PNG)
        try:
            # Try SVG first
            svg_path = Path(__file__).parent.parent / "resouces" / "icon.svg"
            png_path = Path(__file__).parent.parent / "resouces" / "icon.png"

            icon_path = (
                svg_path
                if svg_path.exists()
                else (png_path if png_path.exists() else None)
            )

            if icon_path:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    str(icon_path), 256, 256, True
                )
                texture = Gdk.Texture.new_for_pixbuf(pixbuf)
                logo = Gtk.Picture.new_for_paintable(texture)
                logo.set_size_request(256, 256)
                box.append(logo)
            else:
                print("TFCBM logo not found (tried icon.svg and icon.png)")
        except Exception as e:
            print(f"Could not load splash logo: {e}")

        # App title
        title = Gtk.Label(label="TFCBM")
        title.add_css_class("title-1")
        box.append(title)

        # Subtitle
        subtitle = Gtk.Label(label="The F*cking Clipboard Manager")
        subtitle.add_css_class("dim-label")
        box.append(subtitle)

        # Loading spinner
        spinner = Gtk.Spinner()
        spinner.set_size_request(32, 32)
        spinner.start()
        box.append(spinner)

        # Loading text
        loading_label = Gtk.Label(label="Starting up...")
        loading_label.add_css_class("caption")
        loading_label.add_css_class("dim-label")
        box.append(loading_label)

        self.set_child(box)

        # Center the window on screen
        self.set_modal(False)


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
