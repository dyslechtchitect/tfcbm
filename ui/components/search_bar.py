"""Search bar component with debouncing."""

from typing import Callable, Optional

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk


class SearchBar:
    def __init__(
        self,
        on_search: Callable[[str], None],
        placeholder: str = "Search clipboard items...",
        debounce_ms: int = 1000,
    ):
        self.on_search = on_search
        self.placeholder = placeholder
        self.debounce_ms = debounce_ms
        self.search_timer: Optional[int] = None

    def build(self) -> Gtk.Widget:
        container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        container.set_margin_start(8)
        container.set_margin_end(8)
        container.set_margin_top(8)
        container.set_margin_bottom(4)

        search_entry = Gtk.SearchEntry()
        search_entry.set_hexpand(True)
        search_entry.set_placeholder_text(self.placeholder)
        search_entry.connect("search-changed", self._on_search_changed)
        search_entry.connect("activate", self._on_search_activate)
        container.append(search_entry)

        self.search_entry = search_entry
        return container

    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        if self.search_timer:
            GLib.source_remove(self.search_timer)
            self.search_timer = None

        query = entry.get_text()

        if not query.strip():
            self.on_search("")
            return

        self.search_timer = GLib.timeout_add(
            self.debounce_ms, self._perform_search, query
        )

    def _on_search_activate(self, entry: Gtk.SearchEntry) -> None:
        if self.search_timer:
            GLib.source_remove(self.search_timer)
            self.search_timer = None

        query = entry.get_text()
        self._perform_search(query)

    def _perform_search(self, query: str) -> bool:
        self.search_timer = None
        self.on_search(query)
        return False
