"""Manages user-defined tags (CRUD operations, drag-and-drop)."""

import asyncio
import json
import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional

import gi
from ui.services.ipc_helpers import connect as ipc_connect
from ui.utils.color_utils import sanitize_color

gi.require_version("Gtk", "4.0")

from gi.repository import Gdk, GLib, GObject, Gtk

logger = logging.getLogger("TFCBM.UserTagsManager")


class UserTagsManager:
    """Manages user tag loading, creation, deletion, and drag-and-drop."""

    def __init__(
        self,
        user_tags_group: Any,  # Gtk.ListBox or similar container
        on_refresh_tag_display: Callable[[], None],
        on_item_tag_reload: Callable[[int, Gtk.ListBox, Gtk.ListBox], None],
        window: Any,  # Parent window for dialogs
    ):
        """Initialize UserTagsManager.

        Args:
            user_tags_group: ListBox widget for Tag Manager tab
            on_refresh_tag_display: Callback to refresh tag filter display
            on_item_tag_reload: Callback to reload tags for a clipboard item
            window: Parent window for dialogs
        """
        self.user_tags_group = user_tags_group
        self.on_refresh_tag_display = on_refresh_tag_display
        self.on_item_tag_reload = on_item_tag_reload
        self.window = window

        # State
        self.all_tags: List[Dict] = []
        self.dragged_tag: Optional[Dict] = None
        self.user_tags_load_start_time = 0
        self._user_tag_rows: List[Any] = []  # Track rows for removal

    def load_user_tags(self):
        """Load user-defined tags from server."""
        self.user_tags_load_start_time = time.time()
        logger.info("Starting user tags load...")

        def run_load():
            try:

                async def fetch_tags():
                    uri = ""
                    async with ipc_connect(uri) as conn:
                        request = {"action": "get_tags"}
                        await conn.send(json.dumps(request))

                        response = await conn.recv()
                        data = json.loads(response)

                        if data.get("type") == "tags":
                            all_tags = data.get("tags", [])
                            # Only user-defined tags (filter out system tags)
                            user_tags = [
                                tag
                                for tag in all_tags
                                if not tag.get("is_system", False)
                            ]
                            GLib.idle_add(self._refresh_user_tags_display, user_tags)

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(fetch_tags())
                finally:
                    loop.close()
            except Exception as e:
                logger.error(f"Error loading user tags: {e}")

        threading.Thread(target=run_load, daemon=True).start()

    def create_tag(self, name: str, color: str, parent_window: Gtk.Window):
        """Create a new tag on the server.

        Args:
            name: Tag name
            color: Tag color (hex format)
            parent_window: Parent window for dialogs
        """

        def run_create():
            try:

                async def create_tag_async():
                    uri = ""
                    async with ipc_connect(uri) as conn:
                        request = {
                            "action": "create_tag",
                            "name": name,
                            "color": color,
                        }
                        await conn.send(json.dumps(request))
                        response = await conn.recv()
                        data = json.loads(response)

                        if data.get("success"):
                            logger.info(f"Tag '{name}' created successfully")
                            # Reload user tags display
                            GLib.idle_add(self.load_user_tags)
                            # Refresh tag filter display (via window callback)
                            if hasattr(self.window, 'load_tags'):
                                GLib.idle_add(self.window.load_tags)
                        else:
                            error_msg = data.get("error", "Unknown error")
                            logger.error(f"Failed to create tag: {error_msg}")

                            def show_error():
                                dialog = Gtk.MessageDialog(
                                    transient_for=parent_window,
                                    modal=True,
                                    message_type=Gtk.MessageType.ERROR,
                                    buttons=Gtk.ButtonsType.OK,
                                    text="Error Creating Tag",
                                    secondary_text=f"Failed to create tag: {error_msg}",
                                )
                                dialog.connect("response", lambda d, r: d.close())
                                dialog.present()

                            GLib.idle_add(show_error)

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(create_tag_async())
                finally:
                    loop.close()
            except Exception as e:
                logger.error(f"Error creating tag: {e}")

        threading.Thread(target=run_create, daemon=True).start()

    def delete_tag(self, tag_id: int, parent_window: Gtk.Window):
        """Delete a tag from the server.

        Args:
            tag_id: Tag ID to delete
            parent_window: Parent window for dialogs
        """

        def run_delete():
            try:

                async def delete_tag_async():
                    uri = ""
                    async with ipc_connect(uri) as conn:
                        request = {"action": "delete_tag", "tag_id": tag_id}
                        await conn.send(json.dumps(request))
                        response = await conn.recv()
                        data = json.loads(response)

                        if data.get("success"):
                            logger.info(f"Tag {tag_id} deleted successfully")
                            # Reload user tags display
                            GLib.idle_add(self.load_user_tags)
                            # Refresh tag filter display (via window callback)
                            if hasattr(self.window, 'load_tags'):
                                GLib.idle_add(self.window.load_tags)
                            # Show success notification
                            if hasattr(self.window, 'show_notification'):
                                GLib.idle_add(self.window.show_notification, "Tag deleted")
                            # Force reload of current tab to refresh item displays
                            # Schedule with a delay to ensure load_tags completes first
                            if hasattr(self.window, '_reload_current_tab'):
                                GLib.timeout_add(500, self.window._reload_current_tab)
                        else:
                            error_msg = data.get("error", "Unknown error")
                            logger.error(f"Failed to delete tag: {error_msg}")

                            def show_error():
                                dialog = Gtk.MessageDialog(
                                    transient_for=parent_window,
                                    modal=True,
                                    message_type=Gtk.MessageType.ERROR,
                                    buttons=Gtk.ButtonsType.OK,
                                    text="Error Deleting Tag",
                                    secondary_text=f"Failed to delete tag: {error_msg}",
                                )
                                dialog.connect("response", lambda d, r: d.close())
                                dialog.present()

                            GLib.idle_add(show_error)

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(delete_tag_async())
                finally:
                    loop.close()
            except Exception as e:
                logger.error(f"Error deleting tag: {e}")

        threading.Thread(target=run_delete, daemon=True).start()

    def add_tag_to_item(
        self, tag_id: int, item_id: int, copied_listbox: Gtk.ListBox, pasted_listbox: Gtk.ListBox
    ):
        """Add a tag to a clipboard item.

        Args:
            tag_id: Tag ID to add
            item_id: Item ID to tag
            copied_listbox: Copied items listbox
            pasted_listbox: Pasted items listbox
        """
        logger.info(f"Tag {tag_id} dropped on item {item_id}")

        def run_add_tag():
            try:

                async def add_tag_async():
                    uri = ""
                    async with ipc_connect(uri) as conn:
                        request = {
                            "action": "add_item_tag",
                            "item_id": item_id,
                            "tag_id": int(tag_id),
                        }
                        await conn.send(json.dumps(request))
                        response = await conn.recv()
                        data = json.loads(response)

                        if data.get("success"):
                            logger.info(
                                f"Successfully added tag {tag_id} to item {item_id}"
                            )
                            # Reload item tags via callback
                            GLib.idle_add(
                                self.on_item_tag_reload,
                                item_id,
                                copied_listbox,
                                pasted_listbox,
                            )
                        else:
                            logger.error(
                                f"Failed to add tag: {data.get('error', 'Unknown error')}"
                            )

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(add_tag_async())
                finally:
                    loop.close()
            except Exception as e:
                logger.error(f"Error adding tag: {e}")

        threading.Thread(target=run_add_tag, daemon=True).start()

    def on_tag_drag_prepare(self, drag_source, x, y, tag) -> Gdk.ContentProvider:
        """Prepare data for tag drag operation.

        Args:
            drag_source: Drag source
            x: X coordinate
            y: Y coordinate
            tag: Tag dictionary

        Returns:
            Gdk.ContentProvider with tag ID
        """
        self.dragged_tag = tag
        tag_id = str(tag.get("id"))
        value = GObject.Value(str, tag_id)
        return Gdk.ContentProvider.new_for_value(value)

    def on_tag_drag_begin(self, drag_source, drag):
        """Set drag icon when tag drag begins.

        Args:
            drag_source: Drag source
            drag: Drag object
        """
        widget = drag_source.get_widget()
        drag_source.set_icon(Gtk.WidgetPaintable.new(widget), 0, 0)

    def _refresh_user_tags_display(self, user_tags: List[Dict]) -> bool:
        """Refresh the Tag Manager display with loaded tags.

        Args:
            user_tags: List of user tag dictionaries

        Returns:
            bool: False (for GLib.idle_add)
        """
        load_time = time.time() - self.user_tags_load_start_time
        logger.info(f"User tags loaded in {load_time:.2f}s, refreshing display...")

        # Store tags
        self.all_tags = user_tags

        # Clear existing tag rows from Tag Manager
        for row in self._user_tag_rows:
            self.user_tags_group.remove(row)
        self._user_tag_rows.clear()

        # Add tag rows to Tag Manager tab
        if not user_tags:
            empty_row = Gtk.ListBoxRow()
            row_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            row_box.set_margin_start(12)
            row_box.set_margin_end(12)
            row_box.set_margin_top(8)
            row_box.set_margin_bottom(8)
            title_label = Gtk.Label(label="No custom tags yet")
            title_label.set_halign(Gtk.Align.START)
            row_box.append(title_label)
            subtitle_label = Gtk.Label(label="Create your first tag to organize clipboard items")
            subtitle_label.set_halign(Gtk.Align.START)
            subtitle_label.add_css_class("dim-label")
            subtitle_label.add_css_class("caption")
            row_box.append(subtitle_label)
            empty_row.set_child(row_box)
            self.user_tags_group.append(empty_row)
            self._user_tag_rows.append(empty_row)
        else:
            for tag in user_tags:
                tag_id = tag.get("id")
                tag_name = tag.get("name", "")
                tag_color = tag.get("color", "#9a9996").strip()

                tag_row = Gtk.ListBoxRow()
                row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
                row_box.set_margin_start(12)
                row_box.set_margin_end(12)
                row_box.set_margin_top(8)
                row_box.set_margin_bottom(8)

                # Create a color indicator box
                color_box = Gtk.Box()
                color_box.set_size_request(20, 20)
                color_box.set_valign(Gtk.Align.CENTER)

                # Apply color
                css_provider = Gtk.CssProvider()
                tag_color_clean = sanitize_color(tag_color)
                css_data = f"box {{ background-color: {tag_color_clean}; border-radius: 4px; }}"
                try:
                    css_provider.load_from_string(css_data)
                except Exception as e:
                    logger.error(f"ERROR loading CSS for tag color box: {e}")
                    logger.error(f"  CSS data: {repr(css_data)}")
                    logger.error(f"  Tag: {tag_name}, Color: {repr(tag_color)}")
                color_box.get_style_context().add_provider(
                    css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                )
                row_box.append(color_box)

                # Tag name label
                name_label = Gtk.Label(label=tag_name)
                name_label.set_halign(Gtk.Align.START)
                name_label.set_hexpand(True)
                row_box.append(name_label)

                # Edit button
                edit_button = Gtk.Button()
                edit_button.set_icon_name("document-edit-symbolic")
                edit_button.set_valign(Gtk.Align.CENTER)
                edit_button.add_css_class("flat")
                edit_button.connect(
                    "clicked", lambda b, tid=tag_id: self._on_edit_tag(tid)
                )
                row_box.append(edit_button)

                # Delete button
                delete_button = Gtk.Button()
                delete_button.set_icon_name("user-trash-symbolic")
                delete_button.set_valign(Gtk.Align.CENTER)
                delete_button.add_css_class("flat")
                delete_button.add_css_class("destructive-action")
                delete_button.connect(
                    "clicked", lambda b, tid=tag_id: self._on_delete_tag(tid)
                )
                row_box.append(delete_button)

                tag_row.set_child(row_box)

                # Add drag source for drag-and-drop
                drag_source = Gtk.DragSource.new()
                drag_source.set_actions(Gdk.DragAction.COPY)
                drag_source.connect("prepare", self.on_tag_drag_prepare, tag)
                drag_source.connect("drag-begin", self.on_tag_drag_begin)
                tag_row.add_controller(drag_source)

                self.user_tags_group.append(tag_row)
                self._user_tag_rows.append(tag_row)

        # Refresh tag filter display (to update the filter area)
        self.on_refresh_tag_display()

        logger.info(f"Tag Manager display refreshed with {len(user_tags)} tags")
        return False

    def _on_edit_tag(self, tag_id):
        """Handle edit tag button click - delegates to window handler."""
        if hasattr(self.window, '_on_edit_tag'):
            self.window._on_edit_tag(tag_id)

    def _on_delete_tag(self, tag_id):
        """Handle delete tag button click - delegates to window handler."""
        if hasattr(self.window, '_on_delete_tag'):
            self.window._on_delete_tag(tag_id)
