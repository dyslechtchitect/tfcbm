"""History Loader Manager - Handles IPC data loading for clipboard history."""

import asyncio
import json
import logging
import subprocess
import threading
import time
import traceback
from typing import Callable

import gi
from ui.services.ipc_helpers import connect as ipc_connect, ConnectionClosedError

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from ui.rows.clipboard_item_row import ClipboardItemRow

logger = logging.getLogger("TFCBM.HistoryLoaderManager")


class HistoryLoaderManager:
    """Manages IPC data loading for clipboard history."""

    def __init__(
        self,
        copied_listbox: Gtk.ListBox,
        pasted_listbox: Gtk.ListBox,
        copied_status_label: Gtk.Label,
        pasted_status_label: Gtk.Label,
        copied_loader: Gtk.Widget,
        pasted_loader: Gtk.Widget,
        copied_scrolled: Gtk.ScrolledWindow,
        pasted_scrolled: Gtk.ScrolledWindow,
        window,  # Reference to ClipboardWindow for callbacks
        get_active_filters: Callable,
        get_search_query: Callable,
        page_size: int,
        socket_path: str = "",
    ):
        """Initialize HistoryLoaderManager.

        Args:
            copied_listbox: ListBox for copied items
            pasted_listbox: ListBox for pasted items
            copied_status_label: Status label for copied items
            pasted_status_label: Status label for pasted items
            copied_loader: Loader widget for copied items
            pasted_loader: Loader widget for pasted items
            copied_scrolled: ScrolledWindow for copied items
            pasted_scrolled: ScrolledWindow for pasted items
            window: Reference to ClipboardWindow for callbacks
            get_active_filters: Callback to get active filter set
            get_search_query: Callback to get current search query
            page_size: Number of items per page
            socket_path: IPC socket path
        """
        self.copied_listbox = copied_listbox
        self.pasted_listbox = pasted_listbox
        self.copied_status_label = copied_status_label
        self.pasted_status_label = pasted_status_label
        self.copied_loader = copied_loader
        self.pasted_loader = pasted_loader
        self.copied_scrolled = copied_scrolled
        self.pasted_scrolled = pasted_scrolled
        self.window = window
        self.get_active_filters = get_active_filters
        self.get_search_query = get_search_query
        self.page_size = page_size
        # Use provided socket_path or default to XDG_RUNTIME_DIR
        if not socket_path:
            import os
            runtime_dir = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
            socket_path = os.path.join(runtime_dir, "tfcbm-ipc.sock")
        self.socket_path = socket_path

        # Pagination state
        self.copied_offset = 0
        self.copied_total = 0
        self.copied_has_more = True
        self.copied_loading = False

        self.pasted_offset = 0
        self.pasted_total = 0
        self.pasted_has_more = True
        self.pasted_loading = False

    def load_history(self):
        """Load clipboard history and listen for updates via IPC."""
        self.history_load_start_time = time.time()
        logger.info("Starting initial history load...")

        def run_ipc():
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.ipc_client())
            finally:
                loop.close()

        # Run in background thread
        thread = threading.Thread(target=run_ipc, daemon=True)
        thread.start()

    async def ipc_client(self):
        """IPC client to connect to backend."""
        print(f"Connecting to IPC server at {self.socket_path}...")

        try:
            async with ipc_connect(self.socket_path) as conn:
                print("Connected to IPC server")

                # Request history
                request = {"action": "get_history", "limit": self.page_size}
                if self.get_active_filters():
                    request["filters"] = list(self.get_active_filters())
                    print(
                        f"[FILTER] Sending filters to server: {list(self.get_active_filters())}"
                    )
                await conn.send(json.dumps(request))
                print(
                    f"Requested history with filters: {request.get('filters', 'none')}"
                )

                # Request recently pasted items
                pasted_request = {
                    "action": "get_recently_pasted",
                    "limit": self.page_size,
                }
                if self.get_active_filters():
                    pasted_request["filters"] = list(self.get_active_filters())
                await conn.send(json.dumps(pasted_request))
                print(
                    f"Requested pasted items with filters: {pasted_request.get('filters', 'none')}"
                )

                # Listen for messages
                logger.info("Starting message listener loop...")
                async for message in conn:
                    data = json.loads(message)
                    msg_type = data.get("type")
                    logger.debug(f"Received message type: {msg_type}")

                    if msg_type == "history":
                        # Initial history load
                        items = data.get("items", [])
                        total_count = data.get("total_count", 0)
                        offset = data.get("offset", 0)
                        print(
                            f"Received {len(items)} items from history (total: {total_count})"
                        )
                        GLib.idle_add(
                            self.initial_history_load,
                            items,
                            total_count,
                            offset,
                        )

                    elif msg_type == "recently_pasted":
                        # Pasted history load
                        items = data.get("items", [])
                        total_count = data.get("total_count", 0)
                        offset = data.get("offset", 0)
                        print(
                            f"Received {len(items)} pasted items (total: {total_count})"
                        )
                        GLib.idle_add(
                            self.initial_pasted_load,
                            items,
                            total_count,
                            offset,
                        )

                    elif msg_type == "new_item":
                        # New item added
                        item = data.get("item")
                        if item:
                            print(f"New item received: {item['type']}")
                            GLib.idle_add(self.window.add_item, item)

                    elif msg_type == "item_deleted":
                        # Item deleted
                        item_id = data.get("id")
                        if item_id:
                            GLib.idle_add(self.window.remove_item, item_id)

        except ConnectionClosedError:
            # Normal closure when app exits - suppress error
            logger.info("IPC connection closed normally")
        except StopAsyncIteration:
            logger.info("IPC async iteration stopped")
        except Exception as e:
            logger.error(f"IPC error: {e}")
            traceback.print_exc()
            GLib.idle_add(self.window.show_error, str(e))

    def load_pasted_history(self):
        """Load recently pasted items via IPC."""
        page_size = self.page_size  # Capture for closure

        def run_ipc():
            try:

                async def get_pasted():
                    async with ipc_connect(self.socket_path) as conn:
                        # Request pasted history
                        request = {
                            "action": "get_recently_pasted",
                            "limit": page_size,
                        }
                        # Include active filters
                        if self.get_active_filters():
                            request["filters"] = list(self.get_active_filters())
                            print(
                                f"[FILTER] Requesting pasted items with filters: {list(self.get_active_filters())}"
                            )
                        await conn.send(json.dumps(request))

                        # Wait for response
                        response = await conn.recv()
                        data = json.loads(response)

                        if data.get("type") == "recently_pasted":
                            items = data.get("items", [])
                            print(f"Received {len(items)} pasted items")
                            GLib.idle_add(self.update_pasted_history, items)

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(get_pasted())
                finally:
                    loop.close()

            except Exception as e:
                print(f"Error loading pasted history: {e}")

        # Run in background thread
        thread = threading.Thread(target=run_ipc, daemon=True)
        thread.start()

    def initial_history_load(self, items, total_count, offset):
        """Initial load of copied history with pagination data."""
        if hasattr(self, "history_load_start_time"):
            duration = time.time() - self.history_load_start_time
            logger.info(f"Initial history loaded in {duration:.2f} seconds")
            del self.history_load_start_time

        # Update pagination state
        self.copied_offset = offset
        self.copied_total = total_count
        self.copied_has_more = (offset + len(items)) < total_count

        # Clear existing items
        while True:
            row = self.copied_listbox.get_row_at_index(0)
            if row is None:
                break
            self.copied_listbox.remove(row)

        # Add items (database returns DESC order, append to maintain it)
        for item in items:
            row = ClipboardItemRow(
                item, self.window, search_query=self.get_search_query()
            )
            self.copied_listbox.append(row)  # Append to maintain DESC order

        # Update status label
        current_count = len(items)
        self.copied_status_label.set_label(
            f"Showing {current_count} of {total_count} items"
        )

        # Kill standalone splash screen and show main window
        subprocess.run(
            ["pkill", "-f", "ui/splash.py"], stderr=subprocess.DEVNULL
        )
        self.window.present()

        return False  # Don't repeat

    def initial_pasted_load(self, items, total_count, offset):
        """Initial load of pasted history with pagination data."""
        # Update pagination state
        self.pasted_offset = offset
        self.pasted_total = total_count
        self.pasted_has_more = (offset + len(items)) < total_count

        # Clear existing items
        while True:
            row = self.pasted_listbox.get_row_at_index(0)
            if row is None:
                break
            self.pasted_listbox.remove(row)

        # Add items (database returns DESC order, append to maintain it)
        for item in items:
            row = ClipboardItemRow(
                item,
                self.window,
                show_pasted_time=True,
                search_query=self.get_search_query(),
            )
            self.pasted_listbox.append(row)  # Append to maintain DESC order

        # Update status label
        current_count = len(items)
        self.pasted_status_label.set_label(
            f"Showing {current_count} of {total_count} items"
        )

        # Scroll to top
        vadj = self.pasted_scrolled.get_vadjustment()
        vadj.set_value(0)

        return False  # Don't repeat

    def update_pasted_history(self, history):
        """Update the pasted listbox with pasted items."""
        # Clear existing items
        while True:
            row = self.pasted_listbox.get_row_at_index(0)
            if row is None:
                break
            self.pasted_listbox.remove(row)

        # Add items (database returns DESC order, append to maintain it)
        for item in history:
            row = ClipboardItemRow(
                item,
                self.window,
                show_pasted_time=True,
                search_query=self.get_search_query(),
            )
            self.pasted_listbox.append(row)  # Append to maintain DESC order

        return False  # Don't repeat

    def load_more_copied_items(self):
        """Load more copied items via IPC."""

        def run_ipc():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._fetch_more_items("copied"))
            finally:
                loop.close()

        threading.Thread(target=run_ipc, daemon=True).start()
        return False

    def load_more_pasted_items(self):
        """Load more pasted items via IPC."""

        def run_ipc():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._fetch_more_items("pasted"))
            finally:
                loop.close()

        threading.Thread(target=run_ipc, daemon=True).start()
        return False

    async def _fetch_more_items(self, list_type):
        """Fetch more items from backend via IPC."""
        try:
            async with ipc_connect(self.socket_path) as conn:
                if list_type == "copied":
                    request = {
                        "action": "get_history",
                        "offset": self.copied_offset + self.page_size,
                        "limit": self.page_size,
                    }
                    if self.get_active_filters():
                        request["filters"] = list(self.get_active_filters())
                else:  # pasted
                    request = {
                        "action": "get_recently_pasted",
                        "offset": self.pasted_offset + self.page_size,
                        "limit": self.page_size,
                    }
                    # Include active filters for pasted items too
                    if self.get_active_filters():
                        request["filters"] = list(self.get_active_filters())

                await conn.send(json.dumps(request))
                response = await conn.recv()
                data = json.loads(response)

                if data.get("type") == "history" and list_type == "copied":
                    items = data.get("items", [])
                    total_count = data.get("total_count", 0)
                    offset = data.get("offset", 0)
                    GLib.idle_add(
                        self._append_items_to_listbox,
                        items,
                        total_count,
                        offset,
                        "copied",
                    )
                elif (
                    data.get("type") == "recently_pasted"
                    and list_type == "pasted"
                ):
                    items = data.get("items", [])
                    total_count = data.get("total_count", 0)
                    offset = data.get("offset", 0)
                    GLib.idle_add(
                        self._append_items_to_listbox,
                        items,
                        total_count,
                        offset,
                        "pasted",
                    )

        except Exception as e:
            print(f"IPC error fetching more {list_type} items: {e}")
            traceback.print_exc()
            GLib.idle_add(
                lambda: print(f"Error loading more items: {str(e)}") or False
            )
        finally:
            if list_type == "copied":
                GLib.idle_add(lambda: self.copied_loader.set_visible(False))
                self.copied_loading = False
            else:
                GLib.idle_add(lambda: self.pasted_loader.set_visible(False))
                self.pasted_loading = False

    def _append_items_to_listbox(self, items, total_count, offset, list_type):
        """Append new items to the respective listbox."""
        if list_type == "copied":
            listbox = self.copied_listbox
            self.copied_offset = offset
            self.copied_total = total_count
            self.copied_has_more = (
                self.copied_offset + len(items)
            ) < self.copied_total
            self.copied_loader.set_visible(False)
            self.copied_loading = False
        else:  # pasted
            listbox = self.pasted_listbox
            self.pasted_offset = offset
            self.pasted_total = total_count
            self.pasted_has_more = (
                self.pasted_offset + len(items)
            ) < self.pasted_total
            self.pasted_loader.set_visible(False)
            self.pasted_loading = False

        for item in items:
            row = ClipboardItemRow(
                item,
                self.window,
                show_pasted_time=(list_type == "pasted"),
                search_query=self.get_search_query(),
            )
            listbox.append(row)

        # Count current rows in listbox
        current_count = 0
        index = 0
        while True:
            row = listbox.get_row_at_index(index)
            if row is None:
                break
            current_count += 1
            index += 1

        # Update status label
        if list_type == "copied":
            self.copied_status_label.set_label(
                f"Showing {current_count} of {self.copied_total} items"
            )
        else:
            self.pasted_status_label.set_label(
                f"Showing {current_count} of {self.pasted_total} items"
            )

        return False  # Don't repeat

    def reload_copied_with_filters(self):
        """Reload copied items with current filters."""

        def reload_copied():
            try:

                async def get_history():
                    async with ipc_connect(self.socket_path) as conn:
                        request = {
                            "action": "get_history",
                            "limit": self.page_size,
                        }
                        if self.get_active_filters():
                            request["filters"] = list(self.get_active_filters())
                        await conn.send(json.dumps(request))
                        response = await conn.recv()
                        data = json.loads(response)

                        if data.get("type") == "history":
                            items = data.get("items", [])
                            total_count = data.get("total_count", 0)
                            offset = data.get("offset", 0)
                            GLib.idle_add(
                                self.initial_history_load,
                                items,
                                total_count,
                                offset,
                            )

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(get_history())
                finally:
                    loop.close()
            except Exception as e:
                print(f"[UI] Error reloading history: {e}")

        threading.Thread(target=reload_copied, daemon=True).start()

    def get_pagination_state(self, list_type: str):
        """Get pagination state for a list type.

        Args:
            list_type: "copied" or "pasted"

        Returns:
            dict: Pagination state with keys: offset, total, has_more, loading
        """
        if list_type == "copied":
            return {
                "offset": self.copied_offset,
                "total": self.copied_total,
                "has_more": self.copied_has_more,
                "loading": self.copied_loading,
            }
        else:  # pasted
            return {
                "offset": self.pasted_offset,
                "total": self.pasted_total,
                "has_more": self.pasted_has_more,
                "loading": self.pasted_loading,
            }

    def set_loading(self, list_type: str, loading: bool):
        """Set loading state for a list type.

        Args:
            list_type: "copied" or "pasted"
            loading: True if loading, False otherwise
        """
        if list_type == "copied":
            self.copied_loading = loading
            self.copied_loader.set_visible(loading)
        else:  # pasted
            self.pasted_loading = loading
            self.pasted_loader.set_visible(loading)

    def reset_pagination(self, list_type: str):
        """Reset pagination state for a list type.

        Args:
            list_type: "copied" or "pasted"
        """
        if list_type == "copied":
            self.copied_offset = 0
            self.copied_has_more = True
        else:  # pasted
            self.pasted_offset = 0
            self.pasted_has_more = True
