"""ItemTagManager - Handles all tag-related operations for clipboard items.

This handler manages:
- Tag display in item UI
- Tag popover for managing tags
- Tag drag-and-drop onto items
- Tag add/remove via checkboxes
"""

import asyncio
import json
import logging
import threading

from ui.services.ipc_helpers import connect as ipc_connect
from ui.utils.color_utils import sanitize_color
from gi.repository import GLib, Gtk

from ui.components.items import ItemTags

logger = logging.getLogger("TFCBM.UI")


class ItemTagManager:
    """Handles tag operations for clipboard items."""

    def __init__(
        self,
        item: dict,
        window,
        overlay,
        ws_service,
        on_tags_action: callable,
    ):
        """Initialize the tag manager.

        Args:
            item: The clipboard item data dictionary
            window: The window instance for accessing all_tags
            overlay: The overlay widget where tags are displayed
            ipc_service: ItemIPCService for tag loading
            on_tags_action: Callback for tags button click action
        """
        self.item = item
        self.window = window
        self.overlay = overlay
        self.ipc_service = ws_service
        self.on_tags_action_callback = on_tags_action
        self.tags_widget = None

    def handle_tags_action(self, anchor_to_tags=False):
        """Handle tags button click - show tags popover.

        Args:
            anchor_to_tags: If True, anchor to tags widget; otherwise anchor to button
        """
        self.show_tags_popover(anchor_to_tags=anchor_to_tags)

    def display_tags(self, tags):
        """Display tags in the tags overlay.

        Args:
            tags: List of tag dictionaries to display
        """
        # Remove old tags widget
        if self.tags_widget:
            self.overlay.remove_overlay(self.tags_widget)

        # Create new tags widget
        # When tags are clicked, we want to anchor the popover to the tags widget
        tags_component = ItemTags(tags=tags, on_click=lambda: self.handle_tags_action(anchor_to_tags=True))
        self.tags_widget = tags_component.build()

        # Add new tags widget to overlay
        self.overlay.add_overlay(self.tags_widget)

    def show_tags_popover(self, anchor_to_tags=False):
        """Show popover to manage tags for this item.

        Args:
            anchor_to_tags: If True, anchor to tags widget; otherwise anchor to button
        """
        # Create popover
        popover = Gtk.Popover()

        # Anchor based on where it was clicked from
        if anchor_to_tags and self.tags_widget:
            # Clicked from tags display (bottom left) - anchor above tags
            popover.set_parent(self.tags_widget)
            popover.set_position(Gtk.PositionType.TOP)
        elif hasattr(self, "tags_button") and self.tags_button:
            # Clicked from Manage Tags button (top right) - anchor below button
            popover.set_parent(self.tags_button)
            popover.set_position(Gtk.PositionType.BOTTOM)
        elif self.tags_widget:
            # Fallback to tags widget if button not set
            popover.set_parent(self.tags_widget)
            popover.set_position(Gtk.PositionType.TOP)
        else:
            # Final fallback to overlay
            popover.set_parent(self.overlay)
        popover.set_autohide(True)

        # Content box
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content_box.set_margin_top(12)
        content_box.set_margin_bottom(12)
        content_box.set_margin_start(12)
        content_box.set_margin_end(12)

        # Title
        title = Gtk.Label()
        title.set_markup("<b>Manage Tags</b>")
        title.set_halign(Gtk.Align.START)
        content_box.append(title)

        # Scrollable tag list
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_max_content_height(300)
        scroll.set_propagate_natural_height(True)

        # Tag list box
        tag_list = Gtk.ListBox()
        tag_list.set_selection_mode(Gtk.SelectionMode.NONE)
        tag_list.add_css_class("boxed-list")

        # Get item's current tags
        item_id = self.item.get("id")
        item_tags = self.item.get("tags", [])
        item_tag_ids = [
            tag.get("id") for tag in item_tags if isinstance(tag, dict)
        ]

        # Add all tags as checkbuttons
        if hasattr(self.window, "all_tags"):
            for tag in self.window.all_tags:
                # Skip system tags
                if tag.get("is_system"):
                    continue

                tag_id = tag.get("id")
                tag_name = tag.get("name", "")
                tag_color = tag.get("color", "#9a9996").strip()

                # Create row with checkbutton
                row = Gtk.ListBoxRow()
                row_box = Gtk.Box(
                    orientation=Gtk.Orientation.HORIZONTAL, spacing=12
                )
                row_box.set_margin_top(6)
                row_box.set_margin_bottom(6)
                row_box.set_margin_start(6)
                row_box.set_margin_end(6)

                # Color indicator
                color_box = Gtk.Box()
                color_box.set_size_request(16, 16)
                css_provider = Gtk.CssProvider()
                tag_color_clean = sanitize_color(tag_color)
                css_data = f"box {{ background-color: {tag_color_clean}; border-radius: 3px; }}"
                try:
                    css_provider.load_from_string(css_data)
                except Exception as e:
                    logger.error(f"ERROR loading CSS for tag popover color: {e}")
                    logger.error(f"  CSS data: {repr(css_data)}")
                    logger.error(f"  Tag: {tag_name}, Color: {repr(tag_color)}")
                color_box.get_style_context().add_provider(
                    css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                )
                row_box.append(color_box)

                # Checkbutton with tag name
                check = Gtk.CheckButton()
                check.set_label(tag_name)
                check.set_hexpand(True)
                check.set_active(tag_id in item_tag_ids)
                check.connect(
                    "toggled",
                    lambda cb, tid=tag_id, iid=item_id: self._on_tag_toggle(
                        cb, tid, iid, popover
                    ),
                )
                row_box.append(check)

                row.set_child(row_box)
                tag_list.append(row)

            # No tags message
            if not any(
                not tag.get("is_system") for tag in self.window.all_tags
            ):
                no_tags_label = Gtk.Label()
                no_tags_label.set_markup(
                    "<i>No custom tags available.\nCreate tags in the Tags tab.</i>"
                )
                no_tags_label.set_justify(Gtk.Justification.CENTER)
                content_box.append(no_tags_label)

        scroll.set_child(tag_list)
        content_box.append(scroll)

        popover.set_child(content_box)
        popover.popup()

    def handle_tag_drop(self, drop_target, value, x, y):
        """Handle tag drop on item.

        Args:
            drop_target: The drop target widget
            value: The tag ID being dropped
            x: Drop X coordinate
            y: Drop Y coordinate

        Returns:
            bool: True if drop was successful
        """
        logger.info(f"[TAG_DROP] Received drop - value: {value}, type: {type(value)}")
        try:
            tag_id = value
            item_id = self.item.get("id")
            logger.info(f"[TAG_DROP] Attempting to add tag {tag_id} to item {item_id}")
            if hasattr(self.window, "_on_tag_dropped_on_item"):
                self.window._on_tag_dropped_on_item(tag_id, item_id)
                logger.info(f"[TAG_DROP] Successfully called _on_tag_dropped_on_item")
            else:
                logger.error("[TAG_DROP] window._on_tag_dropped_on_item method not found")
            return True
        except Exception as e:
            logger.error(f"[TAG_DROP] Error in handle_tag_drop: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _on_tag_toggle(self, checkbutton, tag_id, item_id, popover):
        """Handle tag checkbox toggle.

        Args:
            checkbutton: The checkbox widget
            tag_id: ID of the tag being toggled
            item_id: ID of the item
            popover: The popover widget containing the checkbox
        """
        is_active = checkbutton.get_active()

        def send_tag_update():
            try:
                logger.info(f"[TAG_TOGGLE] Starting tag toggle - item_id={item_id}, tag_id={tag_id}, is_active={is_active}")

                async def update_tag():
                    logger.info(f"[TAG_TOGGLE] Connecting to IPC server...")
                    async with ipc_connect() as conn:
                        action = "add_item_tag" if is_active else "remove_item_tag"
                        request = {
                            "action": action,
                            "item_id": item_id,
                            "tag_id": tag_id,
                        }
                        logger.info(f"[TAG_TOGGLE] Sending request: {request}")
                        await conn.send(json.dumps(request))

                        logger.info(f"[TAG_TOGGLE] Waiting for response...")
                        response = await conn.recv()
                        data = json.loads(response)
                        logger.info(f"[TAG_TOGGLE] Received response: {data}")

                        if data.get("type") in ["item_tag_added", "item_tag_removed", "tag_added", "tag_removed"]:
                            logger.info(f"[TAG_TOGGLE] Success! Reloading tags...")
                            # Reload tags for this item
                            GLib.idle_add(self.ipc_service.load_item_tags)
                            # Notify window to refresh if needed
                            if hasattr(self.window, "_on_item_tags_changed"):
                                GLib.idle_add(
                                    self.window._on_item_tags_changed, item_id
                                )
                        else:
                            logger.warning(f"[TAG_TOGGLE] Unexpected response type: {data.get('type')}")

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(update_tag())
                finally:
                    loop.close()
            except Exception as e:
                logger.error(f"[TAG_TOGGLE] Error toggling tag: {e}")
                import traceback
                logger.error(f"[TAG_TOGGLE] Traceback:\n{traceback.format_exc()}")
                # Revert checkbox on error
                GLib.idle_add(lambda: checkbutton.set_active(not is_active))

        threading.Thread(target=send_tag_update, daemon=True).start()

    def set_tags_button(self, tags_button):
        """Set the tags button widget for popover anchoring.

        Args:
            tags_button: The tags button widget
        """
        self.tags_button = tags_button
