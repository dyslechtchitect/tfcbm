"""Item tags display component."""

from typing import Callable, List, Optional

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from ui.utils.color_utils import sanitize_color, hex_to_rgba


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
        tags_box.set_margin_start(8)
        tags_box.set_margin_bottom(2)

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
        tag_color = sanitize_color(tag.get("color", "#9a9996"))

        label = Gtk.Label(label=tag_name)
        label.add_css_class("tag-label")

        # Convert hex color to rgba with 20% opacity
        bg_color = hex_to_rgba(tag_color, 0.2)

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
        try:
            css_provider.load_from_string(css_data)
        except Exception as e:
            print(f"ERROR loading CSS for tag label: {e}")
            print(f"  CSS data: {repr(css_data)}")
            print(f"  Tag color: {repr(tag_color)}")
            print(f"  BG color: {repr(bg_color)}")
        label.get_style_context().add_provider(
            css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        return label
