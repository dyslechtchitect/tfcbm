"""Tag Dialog Manager - Handles tag creation and editing dialogs."""

import asyncio
import json
import logging
import threading
from typing import Callable, List

import gi
import websockets

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

logger = logging.getLogger("TFCBM.TagDialogManager")


class TagDialogManager:
    """Manages tag creation and editing dialogs with color picker UI."""

    # Predefined color palette
    COLORS = [
        "#3584e4",  # Blue
        "#33d17a",  # Green
        "#f6d32d",  # Yellow
        "#ff7800",  # Orange
        "#e01b24",  # Red
        "#9141ac",  # Purple
        "#986a44",  # Brown
        "#5e5c64",  # Gray
    ]

    def __init__(
        self,
        parent_window,
        on_tag_created: Callable[[], None],
        on_tag_updated: Callable[[], None],
        get_all_tags: Callable[[], List[dict]],
        websocket_uri: str = "ws://localhost:8765",
    ):
        """Initialize TagDialogManager.

        Args:
            parent_window: Parent window for dialogs
            on_tag_created: Callback when tag is created
            on_tag_updated: Callback when tag is updated
            get_all_tags: Callback to get all tags list
            websocket_uri: WebSocket server URI
        """
        self.parent_window = parent_window
        self.on_tag_created = on_tag_created
        self.on_tag_updated = on_tag_updated
        self.get_all_tags = get_all_tags
        self.websocket_uri = websocket_uri

    def show_create_dialog(self):
        """Show dialog to create a new tag."""
        dialog = Adw.MessageDialog.new(self.parent_window)
        dialog.set_heading("Create New Tag")
        dialog.set_body("Enter a name for the new tag")

        # Create entry for tag name
        entry_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        entry_box.set_margin_top(12)
        entry_box.set_margin_bottom(12)
        entry_box.set_margin_start(12)
        entry_box.set_margin_end(12)

        name_entry = Gtk.Entry()
        name_entry.set_placeholder_text("Tag name")
        entry_box.append(name_entry)

        # Color picker
        color_label = Gtk.Label()
        color_label.set_text("Choose a color:")
        color_label.set_halign(Gtk.Align.START)
        entry_box.append(color_label)

        color_flow = self._create_color_picker()
        color_flow.select_child(color_flow.get_child_at_index(0))
        entry_box.append(color_flow)

        dialog.set_extra_child(entry_box)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("create", "Create")
        dialog.set_response_appearance("create", Adw.ResponseAppearance.SUGGESTED)

        def on_response(dialog, response):
            if response == "create":
                tag_name = name_entry.get_text().strip()
                if not tag_name:
                    logger.warning("Tag name cannot be empty")
                    return

                selected_color = self._get_selected_color(color_flow, 0)
                self._create_tag_on_server(tag_name, selected_color)

        dialog.connect("response", on_response)
        dialog.present()

    def show_edit_dialog(self, tag_id: int):
        """Show dialog to edit an existing tag.

        Args:
            tag_id: ID of the tag to edit
        """
        # Find the tag
        tag = None
        for t in self.get_all_tags():
            if t.get("id") == tag_id and not t.get("is_system"):
                tag = t
                break

        if not tag:
            logger.warning(f"Tag {tag_id} not found")
            if hasattr(self.parent_window, "show_notification"):
                self.parent_window.show_notification("Tag not found")
            return

        dialog = Adw.MessageDialog.new(self.parent_window)
        dialog.set_heading("Edit Tag")
        dialog.set_body(f"Modify the tag '{tag.get('name')}'")

        # Create entry for tag name
        entry_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        entry_box.set_margin_top(12)
        entry_box.set_margin_bottom(12)
        entry_box.set_margin_start(12)
        entry_box.set_margin_end(12)

        name_entry = Gtk.Entry()
        name_entry.set_text(tag.get("name", ""))
        entry_box.append(name_entry)

        # Color picker
        color_label = Gtk.Label()
        color_label.set_text("Choose a color:")
        color_label.set_halign(Gtk.Align.START)
        entry_box.append(color_label)

        color_flow = self._create_color_picker()

        # Select current color
        current_color_index = 0
        if tag.get("color") in self.COLORS:
            current_color_index = self.COLORS.index(tag.get("color"))
        color_flow.select_child(color_flow.get_child_at_index(current_color_index))
        entry_box.append(color_flow)

        dialog.set_extra_child(entry_box)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("save", "Save")
        dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)

        def on_response(dialog, response):
            if response == "save":
                tag_name = name_entry.get_text().strip()
                if not tag_name:
                    logger.warning("Tag name cannot be empty")
                    return

                selected_color = self._get_selected_color(color_flow, current_color_index)
                self._update_tag_on_server(tag_id, tag_name, selected_color)

        dialog.connect("response", on_response)
        dialog.present()

    def _create_color_picker(self) -> Gtk.FlowBox:
        """Create a color picker FlowBox widget.

        Returns:
            Gtk.FlowBox: Color picker widget
        """
        color_flow = Gtk.FlowBox()
        color_flow.set_selection_mode(Gtk.SelectionMode.SINGLE)
        color_flow.set_max_children_per_line(6)
        color_flow.set_column_spacing(6)
        color_flow.set_row_spacing(6)

        for color in self.COLORS:
            color_btn = Gtk.Button()
            color_btn.set_size_request(40, 40)
            # Store color value on button for later retrieval
            color_btn.color_value = color
            css_provider = Gtk.CssProvider()
            css_data = f"button {{ background-color: {color}; border-radius: 20px; }}"
            css_provider.load_from_data(css_data.encode())
            color_btn.get_style_context().add_provider(
                css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

            # Make button clickable to select its flowbox child
            def on_color_click(btn, flow=color_flow):
                parent = btn.get_parent()
                if parent:
                    flow.select_child(parent)

            color_btn.connect("clicked", on_color_click)
            color_flow.append(color_btn)

        return color_flow

    def _get_selected_color(self, color_flow: Gtk.FlowBox, default_index: int = 0) -> str:
        """Get the selected color from the color picker.

        Args:
            color_flow: Color picker FlowBox
            default_index: Default color index if none selected

        Returns:
            str: Selected color hex code
        """
        selected = color_flow.get_selected_children()
        if selected and len(selected) > 0:
            flow_child = selected[0]
            button = flow_child.get_child()
            if hasattr(button, "color_value"):
                return button.color_value
        return self.COLORS[default_index]

    def _create_tag_on_server(self, name: str, color: str):
        """Create a new tag on the server.

        Args:
            name: Tag name
            color: Tag color (hex format)
        """

        def run_create():
            try:

                async def create_tag():
                    async with websockets.connect(self.websocket_uri) as websocket:
                        request = {
                            "action": "create_tag",
                            "name": name,
                            "color": color,
                        }
                        await websocket.send(json.dumps(request))
                        response = await websocket.recv()
                        data = json.loads(response)

                        if data.get("success"):
                            logger.info(f"Tag '{name}' created successfully")
                            GLib.idle_add(self.on_tag_created)
                        else:
                            error_msg = data.get("error", "Unknown error")
                            logger.error(f"Failed to create tag: {error_msg}")
                            if hasattr(self.parent_window, "show_notification"):
                                GLib.idle_add(
                                    self.parent_window.show_notification,
                                    f"Failed to create tag: {error_msg}",
                                )

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(create_tag())
                finally:
                    loop.close()
            except Exception as e:
                logger.error(f"Error creating tag: {e}")
                if hasattr(self.parent_window, "show_notification"):
                    GLib.idle_add(
                        self.parent_window.show_notification,
                        f"Error creating tag: {e}",
                    )

        threading.Thread(target=run_create, daemon=True).start()

    def _update_tag_on_server(self, tag_id: int, name: str, color: str):
        """Update a tag on the server.

        Args:
            tag_id: Tag ID
            name: New tag name
            color: New tag color (hex format)
        """

        def run_update():
            try:

                async def update_tag():
                    async with websockets.connect(self.websocket_uri) as websocket:
                        request = {
                            "action": "update_tag",
                            "tag_id": tag_id,
                            "name": name,
                            "color": color,
                        }
                        await websocket.send(json.dumps(request))
                        response = await websocket.recv()
                        data = json.loads(response)

                        if data.get("type") == "tag_updated":
                            logger.info(f"Tag updated successfully")
                            if hasattr(self.parent_window, "show_notification"):
                                GLib.idle_add(
                                    self.parent_window.show_notification,
                                    "Tag updated",
                                )
                            GLib.idle_add(self.on_tag_updated)
                        else:
                            error_msg = "Failed to update tag"
                            logger.error(error_msg)
                            if hasattr(self.parent_window, "show_notification"):
                                GLib.idle_add(
                                    self.parent_window.show_notification,
                                    error_msg,
                                )

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(update_tag())
                finally:
                    loop.close()
            except Exception as e:
                logger.error(f"Error updating tag: {e}")
                if hasattr(self.parent_window, "show_notification"):
                    GLib.idle_add(
                        self.parent_window.show_notification,
                        f"Error updating tag: {e}",
                    )

        threading.Thread(target=run_update, daemon=True).start()
