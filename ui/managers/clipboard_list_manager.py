"""Manages loading and displaying clipboard items in lists."""

import asyncio
import logging
from typing import Any, Callable, Dict, List

import gi
from gi.repository import GLib, Gtk

from ui.managers.filter_manager import FilterManager
from ui.managers.pagination_manager import PaginationManager
from ui.managers.search_manager import SearchManager
from ui.managers.sort_manager import SortManager
from ui.rows.clipboard_item_row import ClipboardItemRow
from ui.services.ipc_client import IPCClient

gi.require_version("Gtk", "4.0")


logger = logging.getLogger("TFCBM.ClipboardListManager")


class ClipboardListManager:
    def __init__(
        self,
        ipc_client: IPCClient,
        copied_pagination_manager: PaginationManager,
        pasted_pagination_manager: PaginationManager,
        sort_manager: SortManager,
        search_manager: SearchManager,
        filter_manager: FilterManager,
        copied_listbox: Gtk.ListBox,
        pasted_listbox: Gtk.ListBox,
        copied_loader: Gtk.Widget,
        pasted_loader: Gtk.Widget,
        copied_status_label: Gtk.Label,
        pasted_status_label: Gtk.Label,
        get_current_tab: Callable[[], str],
        show_notification: Callable[[str], None],
        window_instance: Any,  # Reference to the ClipboardWindow instance
    ):
        self.ipc_client = ipc_client
        self.copied_pagination_manager = copied_pagination_manager
        self.pasted_pagination_manager = pasted_pagination_manager
        self.sort_manager = sort_manager
        self.search_manager = search_manager
        self.filter_manager = filter_manager

        self.copied_listbox = copied_listbox
        self.pasted_listbox = pasted_listbox
        self.copied_loader = copied_loader
        self.pasted_loader = pasted_loader
        self.copied_status_label = copied_status_label
        self.pasted_status_label = pasted_status_label

        self.get_current_tab = get_current_tab
        self.show_notification = show_notification
        self.window_instance = window_instance

    def load_initial_history(self):
        logger.info("Starting initial history load from ListManager...")
        GLib.idle_add(
            lambda: asyncio.run(
                self.ipc_client.get_history(
                    offset=0,
                    limit=self.copied_pagination_manager.page_size,
                    sort_order=self.sort_manager.copied_sort.order,
                    filters=self.filter_manager.get_active_filters(),
                )
            )
        )

    def load_pasted_history(self):
        logger.info("Starting initial pasted history load from ListManager...")
        GLib.idle_add(
            lambda: asyncio.run(
                self.ipc_client.get_recently_pasted(
                    offset=0,
                    limit=self.pasted_pagination_manager.page_size,
                    sort_order=self.sort_manager.pasted_sort.order,
                    filters=self.filter_manager.get_active_filters(),
                )
            )
        )

    def load_more_items(self, list_type: str):
        if list_type == "copied":
            pagination_manager = self.copied_pagination_manager
            sort_state = self.sort_manager.copied_sort
            self.copied_listbox
            loader = self.copied_loader
            ipc_method = self.ipc_client.get_history
        else:  # pasted
            pagination_manager = self.pasted_pagination_manager
            sort_state = self.sort_manager.pasted_sort
            self.pasted_listbox
            loader = self.pasted_loader
            ipc_method = self.ipc_client.get_recently_pasted

        if pagination_manager.can_load_more():
            logger.info(f"[UI] Scrolled to bottom of {list_type} list, loading more...")
            pagination_manager.start_loading()
            loader.set_visible(True)

            GLib.idle_add(
                lambda: asyncio.run(
                    ipc_method(
                        offset=pagination_manager.offset,
                        limit=pagination_manager.page_size,
                        sort_order=sort_state.order,
                        filters=self.filter_manager.get_active_filters(),
                    )
                )
            )
        else:
            logger.debug(f"Cannot load more {list_type} items.")

    def _initial_load_callback(
        self,
        items: List[Dict[str, Any]],
        total_count: int,
        offset: int,
        list_type: str,
    ):
        # This callback is for handling the initial load (history or pasted)
        # It's called by _on_ipc_message_handler
        if list_type == "copied":
            pagination_manager = self.copied_pagination_manager
            listbox = self.copied_listbox
            status_label = self.copied_status_label
        else:
            pagination_manager = self.pasted_pagination_manager
            listbox = self.pasted_listbox
            status_label = self.pasted_status_label

        pagination_manager.finish_loading(len(items), total_count)

        # Clear existing items
        while True:
            row = listbox.get_row_at_index(0)
            if row is None:
                break
            listbox.remove(row)

        # Add items (database returns DESC order, append to maintain it)
        for item in items:
            row = ClipboardItemRow(
                item,
                self.window_instance,  # Needs to be the main window to handle clicks
                show_pasted_time=(list_type == "pasted"),
                search_query=self.search_manager.query,
            )
            listbox.append(row)

        # Kill splash screen and show main window on initial copied history load
        if list_type == "copied" and offset == 0:
            import subprocess
            import time

            if hasattr(self.window_instance, 'history_load_start_time'):
                duration = time.time() - self.window_instance.history_load_start_time
                logger.info(f"History loaded in {duration:.2f} seconds")
                del self.window_instance.history_load_start_time

            # Kill standalone splash screen and show main window
            subprocess.run(
                ["pkill", "-f", "ui/splash.py"], stderr=subprocess.DEVNULL
            )
            self.window_instance.present()
            logger.info("Splash screen killed and main window presented")

    def _append_items_callback(
        self,
        items: List[Dict[str, Any]],
        total_count: int,
        offset: int,
        list_type: str,
    ):
        if list_type == "copied":
            listbox = self.copied_listbox
            pagination_manager = self.copied_pagination_manager
            loader = self.copied_loader
            status_label = self.copied_status_label
        else:  # pasted
            listbox = self.pasted_listbox
            pagination_manager = self.pasted_pagination_manager
            loader = self.pasted_loader
            status_label = self.pasted_status_label

        pagination_manager.finish_loading(len(items), total_count)

        loader.set_visible(False)

        for item in items:
            row = ClipboardItemRow(
                item,
                self.window_instance,  # Needs to be the main window to handle clicks
                show_pasted_time=(list_type == "pasted"),
                search_query=self.search_manager.query,
            )
            listbox.append(row)

        # Count current rows in listbox by iterating
        current_count = 0
        index = 0
        while True:
            row = listbox.get_row_at_index(index)
            if row is None:
                break
            current_count += 1
            index += 1

    def handle_ipc_message(self, data: Dict[str, Any]):
        msg_type = data.get("type")

        if msg_type == "history":
            items = data.get("items", [])
            total_count = data.get("total_count", 0)
            offset = data.get("offset", 0)
            logger.debug(f"Received {len(items)} items from history (total: {total_count})")
            if offset == 0:  # Initial load
                GLib.idle_add(
                    self._initial_load_callback,
                    items,
                    total_count,
                    offset,
                    "copied",
                )
            else:  # More items loaded
                GLib.idle_add(
                    self._append_items_callback,
                    items,
                    total_count,
                    offset,
                    "copied",
                )

        elif msg_type == "recently_pasted":
            items = data.get("items", [])
            total_count = data.get("total_count", 0)
            offset = data.get("offset", 0)
            logger.debug(f"Received {len(items)} pasted items (total: {total_count})")
            if offset == 0:  # Initial load
                GLib.idle_add(
                    self._initial_load_callback,
                    items,
                    total_count,
                    offset,
                    "pasted",
                )
            else:  # More items loaded
                GLib.idle_add(
                    self._append_items_callback,
                    items,
                    total_count,
                    offset,
                    "pasted",
                )

        elif msg_type == "new_item":
            item = data.get("item")
            if item:
                logger.debug(f"New item received: {item['type']}")
                GLib.idle_add(self.window_instance.add_item, item)  # Delegate to window to handle adding

        elif msg_type == "item_deleted":
            item_id = data.get("id")
            if item_id:
                GLib.idle_add(self.window_instance.remove_item, item_id)  # Delegate to window to handle removing

        elif msg_type == "file_extensions":
            extensions = data.get("extensions", [])
            GLib.idle_add(self.window_instance._load_file_extensions_callback, extensions)

        elif msg_type == "search_results":
            items = data.get("items", [])
            query = self.search_manager.query
            GLib.idle_add(self.window_instance._display_search_results, items, query)

    def handle_ipc_error(self, error_msg):
        logger.error(f"IPC error in list manager: {error_msg}")
        self.show_notification(f"IPC error: {error_msg}")

    def perform_search(self, query: str):
        logger.info(f"[UI] Searching for: '{query}'")
        GLib.idle_add(
            lambda: asyncio.run(
                self.ipc_client.search(
                    query=query,
                    limit=self.search_manager.page_size,
                    filters=self.filter_manager.get_active_filters(),
                )
            )
        )

    def add_item(self, item: Dict[str, Any]):
        """Add a single new item to the top of the copied list"""
        row = ClipboardItemRow(item, self.window_instance)
        self.copied_listbox.prepend(row)
        # Force the listbox to redraw
        self.copied_listbox.queue_draw()
        # Update pagination total count
        self.copied_pagination_manager.total += 1
        self._update_copied_status()

    def _update_copied_status(self):
        """Update the copied items status label"""
        # Count current items in listbox by iterating through rows
        current_count = 0
        index = 0
        while True:
            row = self.copied_listbox.get_row_at_index(index)
            if row is None:
                break
            current_count += 1
            index += 1
        # Update status label
        pass

    def remove_item(self, item_id: str):
        """Remove an item from both lists by ID"""
        # Remove from copied list
        index = 0
        while True:
            row = self.copied_listbox.get_row_at_index(index)
            if row is None:
                break
            if hasattr(row, "item") and row.item.get("id") == item_id:
                self.copied_listbox.remove(row)
                self.copied_pagination_manager.total -= 1
                self._update_copied_status()
                break
            index += 1

        # Remove from pasted list
        index = 0
        while True:
            row = self.pasted_listbox.get_row_at_index(index)
            if row is None:
                break
            if hasattr(row, "item") and row.item.get("id") == item_id:
                self.pasted_listbox.remove(row)
                self.pasted_pagination_manager.total -= 1
                # No specific status for pasted list
                break
            index += 1

    def handle_filter_change(self):
        """Handle filter changes by reloading current tab and resetting pagination."""
        logger.info("Filter changed. Reloading current tab.")
        current_tab = self.get_current_tab()
        if current_tab == "copied":
            self.copied_pagination_manager.reset()
            # Clear existing items
            while True:
                row = self.copied_listbox.get_row_at_index(0)
                if row is None:
                    break
                self.copied_listbox.remove(row)
            self.load_initial_history()
        elif current_tab == "pasted":
            self.pasted_pagination_manager.reset()
            # Clear existing items
            while True:
                row = self.pasted_listbox.get_row_at_index(0)
                if row is None:
                    break
                self.pasted_listbox.remove(row)
            self.load_pasted_history()
