"""Item header component with timestamp and name editing."""

from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from ui.utils import format_timestamp


class ItemHeader:
    def __init__(
        self,
        item: dict,
        on_name_save: Callable[[int, str], None],
        show_pasted_time: bool = False,
        search_query: str = "",
    ):
        self.item = item
        self.on_name_save = on_name_save
        self.show_pasted_time = show_pasted_time
        self.search_query = search_query
        self.name_entry = None

    def build(self) -> Gtk.Widget:
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        header_box.set_hexpand(False)

        self._add_timestamp(header_box)
        self._add_name_entry(header_box)

        return header_box

    def _add_timestamp(self, container: Gtk.Box) -> None:
        if self.show_pasted_time and "pasted_timestamp" in self.item:
            timestamp = self.item.get("pasted_timestamp", "")
            label_text = f"Pasted: {format_timestamp(timestamp)}"
        else:
            timestamp = self.item.get("timestamp", "")
            label_text = format_timestamp(timestamp)

        if not timestamp:
            return

        time_label = Gtk.Label(label=label_text)
        time_label.add_css_class("dim-label")
        time_label.add_css_class("caption")
        time_label.set_halign(Gtk.Align.START)
        container.append(time_label)

    def _add_name_entry(self, container: Gtk.Box) -> None:
        self.name_entry = Gtk.Entry()
        item_name = self.item.get("name") or ""
        self.name_entry.set_text(item_name)
        self.name_entry.set_placeholder_text("Add name...")
        self.name_entry.set_width_chars(15)
        self.name_entry.set_max_width_chars(30)
        self.name_entry.set_halign(Gtk.Align.START)
        self.name_entry.add_css_class("flat")

        self.name_entry.connect("activate", self._on_name_activate)

        focus_controller = Gtk.EventControllerFocus()
        focus_controller.connect("leave", self._on_name_activate)
        self.name_entry.add_controller(focus_controller)

        container.append(self.name_entry)

    def _on_name_activate(self, widget) -> None:
        if self.name_entry:
            name = self.name_entry.get_text()
            self._save_name(name)

            if hasattr(widget, "get_root"):
                root = widget.get_root()
                if root:
                    root.set_focus(None)

    def _save_name(self, name: str) -> None:
        item_id = self.item["id"]
        self.on_name_save(item_id, name)
