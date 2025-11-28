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
                "released", lambda g, n, x, y: self.on_click()
            )
            tags_gesture.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
            tags_box.add_controller(tags_gesture)

        for tag in self.user_tags:
            tag_label = self._create_tag_label(tag)
            tags_box.append(tag_label)

        return tags_box

    def _create_tag_label(self, tag: dict) -> Gtk.Label:
        tag_name = tag.get("name", "")
        tag_color = tag.get("color", "#9a9996")

        label = Gtk.Label(label=tag_name)
        label.add_css_class("tag-label")

        css_provider = Gtk.CssProvider()
        css_data = (
            f"label {{ color: {tag_color}; "
            f"font-size: 9pt; font-weight: 600; }}"
        )
        css_provider.load_from_data(css_data.encode())
        label.get_style_context().add_provider(
            css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        return label
