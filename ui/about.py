#!/usr/bin/env python3
"""
TFCBM About Dialog - Shows logo, title, and subtitle
"""

from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, GdkPixbuf, Gtk


class AboutWindow(Gtk.Window):
    """About dialog showing logo, title, and subtitle"""

    def __init__(self):
        super().__init__()
        self.set_title("About TFCBM")
        self.set_default_size(500, 600)
        self.set_decorated(True)
        self.set_resizable(False)

        # Create main box with some padding
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Content box with padding
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        content_box.set_halign(Gtk.Align.CENTER)
        content_box.set_valign(Gtk.Align.CENTER)
        content_box.set_margin_top(30)
        content_box.set_margin_bottom(30)
        content_box.set_margin_start(40)
        content_box.set_margin_end(40)

        # Try to load TFCBM logo (try SVG first, then PNG)
        try:
            svg_path = Path(__file__).parent.parent / "icons" / "hicolor" / "scalable" / "apps" / "org.tfcbm.ClipboardManager.svg"

            icon_path = (
                svg_path
                if svg_path.exists()
                else None
            )

            if icon_path:
                texture = Gdk.Texture.new_from_file(Gio.File.new_for_path(str(icon_path)))
                logo = Gtk.Picture.new_for_paintable(texture)
                logo.set_size_request(20, 20)
                content_box.append(logo)
            else:
                print("TFCBM logo not found")
        except Exception as e:
            print(f"Could not load about logo: {e}")

        # App title
        title = Gtk.Label(label="TFCBM")
        title.add_css_class("title-1")
        content_box.append(title)

        # Subtitle
        subtitle = Gtk.Label(label="A clipboard manager that just works.")
        subtitle.add_css_class("title-4")
        subtitle.add_css_class("dim-label")
        content_box.append(subtitle)

        main_box.append(content_box)

        # Close button at the bottom
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        button_box.set_halign(Gtk.Align.CENTER)
        button_box.set_margin_bottom(20)

        close_button = Gtk.Button(label="Close")
        close_button.add_css_class("suggested-action")
        close_button.set_size_request(100, -1)
        close_button.connect("clicked", lambda btn: self.close())
        button_box.append(close_button)

        main_box.append(button_box)

        self.set_child(main_box)
