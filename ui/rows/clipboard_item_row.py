"""Clipboard item row component."""

from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from ui.components.items import ItemActions, ItemContent, ItemHeader, ItemTags


class ClipboardItemRow:
    def __init__(
        self,
        item: dict,
        on_copy: Callable[[], None],
        on_view: Callable[[], None],
        on_save: Callable[[], None],
        on_tags: Callable[[], None],
        on_name_save: Callable[[int, str], None],
        show_pasted_time: bool = False,
        search_query: str = "",
        item_height: int = 150,
    ):
        self.item = item
        self.on_copy = on_copy
        self.on_view = on_view
        self.on_save = on_save
        self.on_tags = on_tags
        self.on_name_save = on_name_save
        self.show_pasted_time = show_pasted_time
        self.search_query = search_query
        self.item_height = item_height

    def build(self) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        row.set_activatable(True)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        main_box.set_hexpand(True)
        main_box.set_vexpand(False)
        main_box.set_size_request(-1, self.item_height)
        main_box.set_margin_start(12)
        main_box.set_margin_end(12)
        main_box.set_margin_top(8)
        main_box.set_margin_bottom(8)
        main_box.set_valign(Gtk.Align.FILL)
        main_box.set_overflow(Gtk.Overflow.HIDDEN)

        card_frame = Gtk.Frame()
        card_frame.set_vexpand(False)
        card_frame.set_hexpand(True)
        card_frame.set_size_request(-1, self.item_height)
        card_frame.add_css_class("clipboard-item-card")
        card_frame.set_child(main_box)

        row.set_size_request(-1, self.item_height)
        row.set_vexpand(False)
        row.set_hexpand(True)

        header = ItemHeader(
            item=self.item,
            on_name_save=self.on_name_save,
            show_pasted_time=self.show_pasted_time,
            search_query=self.search_query,
        )
        main_box.append(header.build())

        content = ItemContent(item=self.item, search_query=self.search_query)
        main_box.append(content.build())

        actions = ItemActions(
            item=self.item,
            on_copy=self.on_copy,
            on_view=self.on_view,
            on_save=self.on_save,
            on_tags=self.on_tags,
        )
        main_box.append(actions.build())

        overlay = Gtk.Overlay()
        overlay.set_child(card_frame)

        tags = ItemTags(tags=self.item.get("tags", []), on_click=self.on_tags)
        overlay.add_overlay(tags.build())

        row.set_child(overlay)

        return row
