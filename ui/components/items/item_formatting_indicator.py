"""Formatting indicator component for items with HTML/RTF formatting."""

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk


class FormattingIndicator:
    """Shows a lightning bolt indicator when item contains formatted text."""

    def __init__(self, item: dict):
        self.item = item
        self.format_type = item.get("format_type")

    def build(self) -> Gtk.Widget | None:
        """Build the formatting indicator widget.

        Returns:
            Gtk.Widget if formatting is present, None otherwise
        """
        if not self.format_type:
            return None

        # Create container box
        indicator_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        indicator_box.set_halign(Gtk.Align.START)
        indicator_box.set_valign(Gtk.Align.CENTER)
        indicator_box.add_css_class("formatting-indicator")

        # Lightning bolt icon
        icon = Gtk.Image.new_from_icon_name("weather-storm-symbolic")
        icon.set_pixel_size(16)
        icon.add_css_class("dim-label")
        indicator_box.append(icon)

        # Format type label
        format_label = Gtk.Label(label=self.format_type.upper())
        format_label.add_css_class("caption")
        format_label.add_css_class("dim-label")
        indicator_box.append(format_label)

        # Set tooltip
        indicator_box.set_tooltip_text("Contains formatting")

        return indicator_box
