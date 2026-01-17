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
        on_favorite_toggle: Callable[[int, bool], None] = None,
        show_pasted_time: bool = False,
        search_query: str = "",
    ):
        self.item = item
        self.on_name_save = on_name_save
        self.on_favorite_toggle = on_favorite_toggle
        self.show_pasted_time = show_pasted_time
        self.search_query = search_query
        self.name_entry = None
        self.favorite_button = None

    def build(self, actions_widget: Gtk.Widget = None) -> Gtk.Widget:
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        header_box.set_hexpand(True)

        self._add_favorite_button(header_box)
        self._add_timestamp(header_box)
        self._add_name_entry(header_box)

        # Add spacer to push actions to the right
        if actions_widget:
            spacer = Gtk.Box()
            spacer.set_hexpand(True)
            header_box.append(spacer)
            header_box.append(actions_widget)

        return header_box

    def _add_favorite_button(self, container: Gtk.Box) -> None:
        """Add a star icon button to toggle favorite status."""
        self.favorite_button = Gtk.Button()
        self.favorite_button.add_css_class("flat")
        self.favorite_button.add_css_class("circular")
        self.favorite_button.set_valign(Gtk.Align.CENTER)

        # Get favorite status from item
        is_favorite = self.item.get("is_favorite", False)

        # Use starred vs non-starred icon
        icon_name = "starred-symbolic" if is_favorite else "non-starred-symbolic"
        self.favorite_button.set_icon_name(icon_name)

        # Set subtle coloring - not too bright
        if is_favorite:
            self.favorite_button.add_css_class("favorite-active")

        self.favorite_button.set_tooltip_text("Toggle favorite" if not is_favorite else "Remove from favorites")

        # Connect to toggle handler
        self.favorite_button.connect("clicked", self._on_favorite_clicked)

        container.append(self.favorite_button)

    def _on_favorite_clicked(self, button: Gtk.Button) -> None:
        """Handle favorite button click."""
        if not self.on_favorite_toggle:
            return

        # Toggle favorite status
        is_favorite = self.item.get("is_favorite", False)
        new_status = not is_favorite

        # Update item dictionary (optimistic update)
        self.item["is_favorite"] = new_status

        # Update button appearance
        icon_name = "starred-symbolic" if new_status else "non-starred-symbolic"
        button.set_icon_name(icon_name)

        if new_status:
            button.add_css_class("favorite-active")
        else:
            button.remove_css_class("favorite-active")

        button.set_tooltip_text("Remove from favorites" if new_status else "Toggle favorite")

        # Call the toggle callback
        item_id = self.item["id"]
        self.on_favorite_toggle(item_id, new_status)

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
