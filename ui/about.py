#!/usr/bin/env python3
"""
TFCBM About Dialog - Shows version and information
"""

import gi
from pathlib import Path

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GdkPixbuf, Gdk, GLib

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

        # Keyboard shortcut section
        shortcut_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        shortcut_box.set_halign(Gtk.Align.CENTER)

        # Keys container
        keys_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        keys_box.set_halign(Gtk.Align.CENTER)

        # Ctrl key
        ctrl_key = self._create_key_widget("Ctrl")
        keys_box.append(ctrl_key)
        self.ctrl_key = ctrl_key  # Store for animation

        # Plus sign
        plus_label = Gtk.Label(label="+")
        plus_label.add_css_class("title-1")
        keys_box.append(plus_label)

        # Backtick/Tilde key
        backtick_key = self._create_key_widget("`\n~", is_dual=True)
        keys_box.append(backtick_key)
        self.backtick_key = backtick_key  # Store for animation

        shortcut_box.append(keys_box)

        # Instruction text
        instruction_label = Gtk.Label()
        instruction_label.set_markup(
            "<b>Hit Ctrl + ` to bring TFCBM to life.</b>"
        )
        instruction_label.set_justify(Gtk.Justification.CENTER)
        shortcut_box.append(instruction_label)

        content_box.append(shortcut_box)

        # Start animation
        self.animation_state = 0
        GLib.timeout_add(100, self._animate_keys)

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

    def _create_key_widget(self, text, is_dual=False):
        """Create a keyboard key widget"""
        # Frame for the key
        key_frame = Gtk.Frame()
        key_frame.add_css_class("keyboard-key")

        # Inner box with padding - vertically centered
        key_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        key_box.set_margin_top(16)
        key_box.set_margin_bottom(16)
        key_box.set_margin_start(24)
        key_box.set_margin_end(24)
        key_box.set_valign(Gtk.Align.CENTER)

        # Label - vertically centered
        key_label = Gtk.Label(label=text)
        key_label.set_valign(Gtk.Align.CENTER)
        key_label.set_halign(Gtk.Align.CENTER)
        if is_dual:
            key_label.add_css_class("title-2")
        else:
            key_label.add_css_class("title-3")
        key_box.append(key_label)

        key_frame.set_child(key_box)
        return key_frame

    def _animate_keys(self):
        """Animate the keyboard keys with a pulsing effect"""
        import math

        # Increment animation state
        self.animation_state += 1

        # Calculate scale using sine wave for smooth pulsing
        # Period of ~20 iterations (2 seconds at 100ms intervals)
        scale = 1.0 + 0.1 * math.sin(self.animation_state * 0.3)

        # Apply scaling effect by adjusting opacity
        # We'll pulse between 0.7 and 1.0 opacity
        opacity = 0.85 + 0.15 * math.sin(self.animation_state * 0.3)

        # Apply opacity to keys
        self.ctrl_key.set_opacity(opacity)
        self.backtick_key.set_opacity(opacity)

        # Continue animation
        return True

    def _on_content_clicked(self, gesture, n_press, x, y):
        """Close window when content area is clicked"""
        self.close()
