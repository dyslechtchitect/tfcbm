"""Search manager - Handles search functionality with debouncing."""

import asyncio
import json
import logging
import threading
import traceback
from typing import Callable, Dict, List, Optional, Set

import gi
import websockets

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from ui.rows.clipboard_item_row import ClipboardItemRow

logger = logging.getLogger("TFCBM.SearchManager")


class SearchManager:
    """Manages search state and operations with 200ms debouncing."""

    def __init__(
        self,
        copied_listbox: Gtk.ListBox,
        pasted_listbox: Gtk.ListBox,
        copied_status_label: Gtk.Label,
        pasted_status_label: Gtk.Label,
        get_current_tab: Callable[[], str],
        jump_to_top: Callable[[str], None],
        window,  # Reference to ClipboardWindow for ClipboardItemRow
        on_notification: Callable[[str], None],
        websocket_uri: str = "ws://localhost:8765",
        search_limit: int = 100,
        debounce_ms: int = 200,
    ):
        """Initialize SearchManager.

        Args:
            copied_listbox: ListBox for copied items
            pasted_listbox: ListBox for pasted items
            copied_status_label: Status label for copied items
            pasted_status_label: Status label for pasted items
            get_current_tab: Callback to get current active tab
            jump_to_top: Callback to scroll to top
            window: Reference to ClipboardWindow for ClipboardItemRow
            on_notification: Callback to show notifications
            websocket_uri: WebSocket server URI
            search_limit: Maximum number of search results
            debounce_ms: Debounce delay in milliseconds (default 200ms)
        """
        self.copied_listbox = copied_listbox
        self.pasted_listbox = pasted_listbox
        self.copied_status_label = copied_status_label
        self.pasted_status_label = pasted_status_label
        self.get_current_tab = get_current_tab
        self.jump_to_top = jump_to_top
        self.window = window
        self.on_notification = on_notification
        self.websocket_uri = websocket_uri
        self.search_limit = search_limit
        self.debounce_ms = debounce_ms

        # Search state
        self.query: str = ""
        self.timer: Optional[int] = None
        self.active: bool = False
        self.results: List[Dict] = []

    def on_search_changed(self, entry: Gtk.SearchEntry, get_active_filters: Callable[[], Set[str]]):
        """Handle search entry text changes with debouncing.

        Args:
            entry: The search entry widget
            get_active_filters: Callback to get active content filters
        """
        # Cancel existing timer if any
        if self.timer:
            GLib.source_remove(self.timer)
            self.timer = None

        query = entry.get_text().strip()

        # If query is empty, clear search and restore normal view
        if not query:
            self.query = ""
            self.active = False
            self.results = []
            # Signal to restore normal view (handled by window)
            return "CLEAR"

        # Set up debounce delay before searching
        self.timer = GLib.timeout_add(self.debounce_ms, self._perform_search, query, get_active_filters)
        return "DEBOUNCE"

    def on_search_activate(self, entry: Gtk.SearchEntry, get_active_filters: Callable[[], Set[str]]):
        """Handle Enter key press - search immediately.

        Args:
            entry: The search entry widget
            get_active_filters: Callback to get active content filters
        """
        # Cancel debounce timer
        if self.timer:
            GLib.source_remove(self.timer)
            self.timer = None

        query = entry.get_text().strip()
        if query:
            self._perform_search(query, get_active_filters)

    def _perform_search(self, query: str, get_active_filters: Callable[[], Set[str]]) -> bool:
        """Perform the actual search via WebSocket.

        Args:
            query: Search query string
            get_active_filters: Callback to get active content filters

        Returns:
            bool: False (for GLib.timeout_add)
        """
        self.query = query
        self.timer = None  # Clear timer reference

        logger.info(f"Searching for: '{query}'")

        active_filters = get_active_filters()

        def run_search():
            try:

                async def search():
                    async with websockets.connect(
                        self.websocket_uri, max_size=5 * 1024 * 1024
                    ) as websocket:
                        request = {
                            "action": "search",
                            "query": query,
                            "limit": self.search_limit,
                        }
                        # Include active filters in search request
                        if active_filters:
                            request["filters"] = list(active_filters)
                            logger.info(f"Searching with filters: {list(active_filters)}")

                        await websocket.send(json.dumps(request))
                        response = await websocket.recv()
                        data = json.loads(response)

                        if data.get("type") == "search_results":
                            items = data.get("items", [])
                            result_count = data.get("count", 0)
                            logger.info(f"Search results: {result_count} items")
                            # Store results and mark search as active
                            self.results = items
                            self.active = True
                            # Display results directly
                            GLib.idle_add(self.display_results, items, query)

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(search())
                finally:
                    loop.close()
            except Exception as e:
                logger.error(f"Search error: {e}")
                traceback.print_exc()
                GLib.idle_add(
                    self.on_notification, f"Search error: {str(e)}"
                )

        threading.Thread(target=run_search, daemon=True).start()
        return False  # Don't repeat timer

    def display_results(self, items: List[Dict], query: str) -> bool:
        """Display search results in the current tab.

        Args:
            items: Search result items
            query: Search query string

        Returns:
            bool: False (for GLib.idle_add)
        """
        # Determine which listbox to update based on current tab
        current_tab = self.get_current_tab()
        if current_tab == "pasted":
            listbox = self.pasted_listbox
            status_label = self.pasted_status_label
            show_pasted_time = True
        else:  # copied
            listbox = self.copied_listbox
            status_label = self.copied_status_label
            show_pasted_time = False

        # Clear existing items
        while True:
            row = listbox.get_row_at_index(0)
            if row is None:
                break
            listbox.remove(row)

        # Display search results or empty message
        if items:
            for item in items:
                row = ClipboardItemRow(
                    item,
                    self.window,
                    show_pasted_time=show_pasted_time,
                    search_query=query,
                )
                listbox.append(row)
            status_label.set_label(
                f"Search: {len(items)} results for '{query}'"
            )
        else:
            # Show empty results message
            empty_box = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=12
            )
            empty_box.set_valign(Gtk.Align.CENTER)
            empty_box.set_margin_top(60)
            empty_box.set_margin_bottom(60)

            empty_label = Gtk.Label(label="No results found")
            empty_label.add_css_class("title-2")
            empty_box.append(empty_label)

            hint_label = Gtk.Label(label=f"No clipboard items match '{query}'")
            hint_label.add_css_class("dim-label")
            empty_box.append(hint_label)

            listbox.append(empty_box)
            status_label.set_label(f"Search: 0 results for '{query}'")

        listbox.queue_draw()
        # Scroll to top to ensure results are visible
        self.jump_to_top(current_tab)

        return False

    def clear(self):
        """Clear search state."""
        self.query = ""
        self.active = False
        self.results = []
        if self.timer:
            GLib.source_remove(self.timer)
            self.timer = None

    def is_active(self) -> bool:
        """Check if search is currently active.

        Returns:
            bool: True if search is active
        """
        return self.active

    def get_query(self) -> str:
        """Get current search query.

        Returns:
            str: Current search query
        """
        return self.query

    def get_results(self) -> List[Dict]:
        """Get current search results.

        Returns:
            List[Dict]: Current search results
        """
        return self.results.copy()
