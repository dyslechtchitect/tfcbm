#!/usr/bin/env python3
"""
TFCBM About Dialog - Shows version and information
"""

import gi
from pathlib import Path

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GdkPixbuf, Gdk

# Version information
VERSION = "1.0.0"

class AboutWindow(Gtk.Window):
    """About dialog showing version, description, and haiku"""

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
            svg_path = Path(__file__).parent.parent / "resouces" / "tfcbm.svg"
            png_path = Path(__file__).parent.parent / "resouces" / "tfcbm.png"

            icon_path = svg_path if svg_path.exists() else (png_path if png_path.exists() else None)

            if icon_path:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(icon_path), 200, 200, True)
                texture = Gdk.Texture.new_for_pixbuf(pixbuf)
                logo = Gtk.Picture.new_for_paintable(texture)
                logo.set_size_request(200, 200)
                content_box.append(logo)
            else:
                print("TFCBM logo not found (tried tfcbm.svg and tfcbm.png)")
        except Exception as e:
            print(f"Could not load about logo: {e}")

        # App title
        title = Gtk.Label(label="TFCBM")
        title.add_css_class("title-1")
        content_box.append(title)

        # Subtitle
        subtitle = Gtk.Label(label="The F*cking Clipboard Manager")
        subtitle.add_css_class("title-4")
        subtitle.add_css_class("dim-label")
        content_box.append(subtitle)

        # Version
        version_label = Gtk.Label(label=f"Version {VERSION}")
        version_label.add_css_class("caption")
        version_label.add_css_class("dim-label")
        content_box.append(version_label)

        # Separator
        separator1 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        separator1.set_margin_top(10)
        separator1.set_margin_bottom(10)
        content_box.append(separator1)

        # Inspiring paragraph
        description_label = Gtk.Label()
        description_label.set_markup(
            "<b>A clipboard manager that just works.</b>\n\n"
            "TFCBM is your faithful companion in the digital realm, "
            "tirelessly capturing every snippet, every fragment of text and image "
            "that passes through your clipboard. No more losing that perfect quote, "
            "that crucial code snippet, or that hilarious meme. "
            "Your clipboard history is now your superpower."
        )
        description_label.set_wrap(True)
        description_label.set_justify(Gtk.Justification.CENTER)
        description_label.set_max_width_chars(50)
        content_box.append(description_label)

        # Separator
        separator2 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        separator2.set_margin_top(10)
        separator2.set_margin_bottom(10)
        content_box.append(separator2)

        # Haiku
        haiku_label = Gtk.Label()
        haiku_label.set_markup(
            "<i>Copy, paste, remember—\n"
            "Your clipboard never forgets now,\n"
            "F*cking brilliant tool.</i>"
        )
        haiku_label.set_wrap(True)
        haiku_label.set_justify(Gtk.Justification.CENTER)
        haiku_label.add_css_class("dim-label")
        content_box.append(haiku_label)

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

        # Make the window close on any click in the content area
        click_gesture = Gtk.GestureClick.new()
        click_gesture.connect("released", self._on_content_clicked)
        content_box.add_controller(click_gesture)

    def _on_content_clicked(self, gesture, n_press, x, y):
        """Close window when content area is clicked"""
        self.close()
