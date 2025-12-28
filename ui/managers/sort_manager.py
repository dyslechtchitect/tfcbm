"""Sort manager - Handles sort order state and operations."""

import asyncio
import json
import logging
import threading
from typing import Callable

import gi
import websockets

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

logger = logging.getLogger("TFCBM.SortManager")


class SortManager:
    """Manages sort order state and operations for copied and pasted tabs."""

    def __init__(
        self,
        sort_button: Gtk.Button,
        on_history_load: Callable[[list, int, int], None],
        on_pasted_load: Callable[[list, int, int], None],
        get_active_filters: Callable[[], set],
        page_size: int,
        websocket_uri: str = "ws://localhost:8765",
    ):
        """Initialize SortManager.

        Args:
            sort_button: Toolbar sort button widget
            on_history_load: Callback to load copied history (items, total, offset)
            on_pasted_load: Callback to load pasted history (items, total, offset)
            get_active_filters: Callback to get active content filters
            page_size: Number of items per page
            websocket_uri: WebSocket server URI
        """
        self.sort_button = sort_button
        self.on_history_load = on_history_load
        self.on_pasted_load = on_pasted_load
        self.get_active_filters = get_active_filters
        self.page_size = page_size
        self.websocket_uri = websocket_uri

        # Sort state
        self.copied_sort_order = "DESC"  # Default: newest first
        self.pasted_sort_order = "DESC"  # Default: newest first

    def toggle_sort(self, list_type: str):
        """Toggle sort order for the specified list.

        Args:
            list_type: Either "copied" or "pasted"
        """
        if list_type == "copied":
            # Toggle sort order
            self.copied_sort_order = (
                "ASC" if self.copied_sort_order == "DESC" else "DESC"
            )

            # Update toolbar button icon and tooltip
            if self.copied_sort_order == "DESC":
                self.sort_button.set_icon_name("view-sort-descending-symbolic")
                self.sort_button.set_tooltip_text("Newest first ↓")
            else:
                self.sort_button.set_icon_name("view-sort-ascending-symbolic")
                self.sort_button.set_tooltip_text("Oldest first ↑")

            # Reload data with new sort order
            self._reload_copied_with_sort()

        elif list_type == "pasted":
            # Toggle sort order
            self.pasted_sort_order = (
                "ASC" if self.pasted_sort_order == "DESC" else "DESC"
            )

            # Update toolbar button icon and tooltip
            if self.pasted_sort_order == "DESC":
                self.sort_button.set_icon_name("view-sort-descending-symbolic")
                self.sort_button.set_tooltip_text("Newest first ↓")
            else:
                self.sort_button.set_icon_name("view-sort-ascending-symbolic")
                self.sort_button.set_tooltip_text("Oldest first ↑")

            # Reload data with new sort order
            self._reload_pasted_with_sort()

    def get_copied_sort_order(self) -> str:
        """Get current copied tab sort order.

        Returns:
            str: Either "ASC" or "DESC"
        """
        return self.copied_sort_order

    def get_pasted_sort_order(self) -> str:
        """Get current pasted tab sort order.

        Returns:
            str: Either "ASC" or "DESC"
        """
        return self.pasted_sort_order

    def _reload_copied_with_sort(self):
        """Reload copied items with current sort order."""

        def reload():
            try:

                async def get_sorted_history():
                    async with websockets.connect(
                        self.websocket_uri, max_size=5 * 1024 * 1024
                    ) as websocket:
                        request = {
                            "action": "get_history",
                            "limit": self.page_size,
                            "sort_order": self.copied_sort_order,
                        }
                        active_filters = self.get_active_filters()
                        if active_filters:
                            request["filters"] = list(active_filters)
                        await websocket.send(json.dumps(request))
                        response = await websocket.recv()
                        data = json.loads(response)

                        if data.get("type") == "history":
                            items = data.get("items", [])
                            total_count = data.get("total_count", 0)
                            offset = data.get("offset", 0)
                            GLib.idle_add(
                                self.on_history_load,
                                items,
                                total_count,
                                offset,
                            )

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(get_sorted_history())
                finally:
                    loop.close()
            except Exception as e:
                logger.error(f"Error reloading sorted history: {e}")

        threading.Thread(target=reload, daemon=True).start()

    def _reload_pasted_with_sort(self):
        """Reload pasted items with current sort order."""

        def reload():
            try:

                async def get_sorted_pasted():
                    async with websockets.connect(
                        self.websocket_uri, max_size=5 * 1024 * 1024
                    ) as websocket:
                        request = {
                            "action": "get_recently_pasted",
                            "limit": self.page_size,
                            "sort_order": self.pasted_sort_order,
                        }
                        # Include active filters
                        active_filters = self.get_active_filters()
                        if active_filters:
                            request["filters"] = list(active_filters)
                        await websocket.send(json.dumps(request))
                        response = await websocket.recv()
                        data = json.loads(response)

                        if data.get("type") == "recently_pasted":
                            items = data.get("items", [])
                            total_count = data.get("total_count", 0)
                            offset = data.get("offset", 0)
                            GLib.idle_add(
                                self.on_pasted_load,
                                items,
                                total_count,
                                offset,
                            )

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(get_sorted_pasted())
                finally:
                    loop.close()
            except Exception as e:
                logger.error(f"Error reloading sorted pasted: {e}")

        threading.Thread(target=reload, daemon=True).start()
