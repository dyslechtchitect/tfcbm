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

logger = logging.getLogger("TFCBM.SearchManager")


class SearchManager:
    """Manages search state and operations with 200ms debouncing."""

    def __init__(
        self,
        on_display_results: Callable[[List[Dict], str], None],
        on_notification: Callable[[str], None],
        websocket_uri: str = "ws://localhost:8765",
        search_limit: int = 100,
        debounce_ms: int = 200,
    ):
        """Initialize SearchManager.

        Args:
            on_display_results: Callback to display search results (items, query)
            on_notification: Callback to show notifications
            websocket_uri: WebSocket server URI
            search_limit: Maximum number of search results
            debounce_ms: Debounce delay in milliseconds (default 200ms)
        """
        self.on_display_results = on_display_results
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
                            # Display results via callback
                            GLib.idle_add(self.on_display_results, items, query)

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
