"""Item tags display component."""

from typing import Callable, List, Optional

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk


class ItemTags:
    def __init__(
        self, tags: List[dict], on_click: Optional[Callable[[], None]] = None
    ):
        self.tags = tags
        self.on_click = on_click
        self.user_tags = [
            tag for tag in tags if not tag.get("is_system", False)
        ]

    def build(self) -> Gtk.Widget:
        tags_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        tags_box.set_halign(Gtk.Align.START)
        tags_box.set_valign(Gtk.Align.END)
        tags_box.set_margin_start(24)
        tags_box.set_margin_bottom(16)

        if self.on_click:
            tags_gesture = Gtk.GestureClick.new()
            tags_gesture.connect(
                "released", self._on_tags_clicked
            )
            tags_gesture.set_propagation_phase(Gtk.PropagationPhase.BUBBLE)
            tags_box.add_controller(tags_gesture)

        for tag in self.user_tags:
            tag_label = self._create_tag_label(tag)
            tags_box.append(tag_label)

        return tags_box

    def _on_tags_clicked(self, gesture, n_press, x, y):
        """Handle tags click and prevent propagation to card."""
        # Call the callback
        if self.on_click:
            self.on_click()
        # Stop event propagation so card doesn't get clicked
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)

    def _create_tag_label(self, tag: dict) -> Gtk.Label:
        tag_name = tag.get("name", "")
        tag_color = tag.get("color", "#9a9996")

        label = Gtk.Label(label=tag_name)
        label.add_css_class("tag-label")

        # Convert hex color to rgba with 20% opacity
        # Parse hex color (supports #RGB and #RRGGBB)
        color_hex = tag_color.lstrip("#")
        if len(color_hex) == 3:
            r = int(color_hex[0] * 2, 16)
            g = int(color_hex[1] * 2, 16)
            b = int(color_hex[2] * 2, 16)
        else:
            r = int(color_hex[0:2], 16)
            g = int(color_hex[2:4], 16)
            b = int(color_hex[4:6], 16)

        bg_color = f"rgba({r}, {g}, {b}, 0.2)"

        css_provider = Gtk.CssProvider()
        css_data = (
            f"label {{ "
            f"color: {tag_color}; "
            f"background-color: {bg_color}; "
            f"border-radius: 4px; "
            f"padding: 2px 6px; "
            f"font-size: 8pt; "
            f"font-weight: 600; "
            f"}}"
        )
        css_provider.load_from_data(css_data.encode())
        label.get_style_context().add_provider(
            css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        return label
