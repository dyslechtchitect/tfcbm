"""Tag Display Manager - Handles rendering and interaction with tag filter area."""

import logging
from typing import Callable, Dict, List, Set

import gi
from ui.utils.color_utils import sanitize_color, hex_to_rgba

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Gio", "2.0")
from gi.repository import Gdk, Gio, Gtk

logger = logging.getLogger("TFCBM.TagDisplayManager")


class TagDisplayManager:
    """Manages tag display area including rendering, selection, and filtering."""

    def __init__(
        self,
        tag_flowbox,
        tag_filter_manager,
        copied_listbox: Gtk.ListBox,
        pasted_listbox: Gtk.ListBox,
        get_current_tab: Callable[[], str],
        on_tag_drag_prepare: Callable,
        on_tag_drag_begin: Callable,
        window=None,
    ):
        """Initialize TagDisplayManager.

        Args:
            tag_flowbox: Box widget for displaying tags (horizontal layout)
            tag_filter_manager: TagFilterManager instance for handling filtering
            copied_listbox: ListBox for copied items
            pasted_listbox: ListBox for pasted items
            get_current_tab: Callback to get current active tab
            on_tag_drag_prepare: Callback for tag drag prepare event
            on_tag_drag_begin: Callback for tag drag begin event
            window: Reference to the main window
        """
        self.tag_flowbox = tag_flowbox  # Actually a Box now, not FlowBox
        self.tag_filter_manager = tag_filter_manager
        self.copied_listbox = copied_listbox
        self.pasted_listbox = pasted_listbox
        self.get_current_tab = get_current_tab
        self.on_tag_drag_prepare = on_tag_drag_prepare
        self.on_tag_drag_begin = on_tag_drag_begin
        self.window = window

        # State
        self.tag_buttons: Dict[int, Gtk.Button] = {}
        self.all_tags: List[Dict] = []

    def refresh_display(self, all_tags: List[Dict]):
        """Refresh the tag display area with updated tags.

        Args:
            all_tags: List of all tags including system tags
        """
        self.all_tags = all_tags

        # Clear existing tags
        while True:
            child = self.tag_flowbox.get_first_child()
            if not child:
                break
            self.tag_flowbox.remove(child)

        self.tag_buttons = {}

        # Filter out system tags - only show custom user tags
        user_tags = [tag for tag in all_tags if not tag.get("is_system", False)]

        # Show empty state if no user tags
        if not user_tags:
            empty_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            empty_box.set_halign(Gtk.Align.END)
            empty_box.set_margin_start(12)
            empty_box.set_margin_end(12)

            empty_label = Gtk.Label(label="Psst, you, yeah you... add tags here ... ")
            empty_label.add_css_class("dim-label")
            empty_box.append(empty_label)

            # Add an animated arrow pointing right
            arrow_label = Gtk.Label(label="→")
            arrow_label.add_css_class("dim-label")
            arrow_label.add_css_class("arrow-nudge")
            css_provider = Gtk.CssProvider()
            css_data = """
                @keyframes nudge-arrow {
                    0%, 100% { margin-left: 0px; opacity: 0.4; }
                    50% { margin-left: 8px; opacity: 1.0; }
                }
                label.arrow-nudge {
                    font-size: 14pt;
                    animation: nudge-arrow 1.5s ease-in-out infinite;
                }
            """
            css_provider.load_from_string(css_data)
            arrow_label.get_style_context().add_provider(
                css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
            empty_box.append(arrow_label)
            #
            # plus_label = Gtk.Label(label="button")
            # plus_label.add_css_class("dim-label")
            # empty_box.append(plus_label)

            self.tag_flowbox.append(empty_box)
            return

        # Add tag buttons
        for tag in user_tags:
            tag_id = tag.get("id")
            tag_name = tag.get("name", "")
            tag_color = tag.get("color", "#9a9996")
            is_selected = tag_id in self.tag_filter_manager.get_selected_tag_ids()

            # Create button for tag
            btn = Gtk.Button.new_with_label(tag_name)
            btn.add_css_class("pill")

            # Apply color styling - selected tags colored, unselected with weak color tint
            css_provider = Gtk.CssProvider()
            # Sanitize color value
            tag_color_clean = sanitize_color(tag_color)
            if is_selected:
                bg_color = hex_to_rgba(tag_color_clean, 0.25)
                border_color = hex_to_rgba(tag_color_clean, 0.4)
                css_data = f"button.pill {{ background-color: {bg_color}; color: {tag_color_clean}; font-size: 9pt; font-weight: normal; padding: 2px 8px; min-height: 20px; border: 1px solid {border_color}; border-radius: 2px; }}"
            else:
                # Unselected: weak color tint (very subtle alpha on the tag color)
                bg_color = hex_to_rgba(tag_color_clean, 0.06)
                text_color = hex_to_rgba(tag_color_clean, 0.4)
                border_color = hex_to_rgba(tag_color_clean, 0.15)
                css_data = f"button.pill {{ background-color: {bg_color}; color: {text_color}; font-size: 9pt; font-weight: normal; padding: 2px 8px; min-height: 20px; border: 1px solid {border_color}; border-radius: 2px; }}"
            try:
                css_provider.load_from_string(css_data)
            except Exception as e:
                logger.error(f"ERROR loading CSS for tag button: {e}")
                logger.error(f"  CSS data: {repr(css_data)}")
                logger.error(f"  Tag: {tag_name}, Color: {repr(tag_color)}")
            btn.get_style_context().add_provider(
                css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

            # Add drag source for drag-and-drop
            drag_source = Gtk.DragSource.new()
            drag_source.set_actions(Gdk.DragAction.COPY)
            drag_source.connect("prepare", self.on_tag_drag_prepare, tag)
            drag_source.connect("drag-begin", self.on_tag_drag_begin)
            btn.add_controller(drag_source)

            btn.connect("clicked", lambda b, tid=tag_id: self._on_tag_clicked(tid))

            # Add right-click menu
            right_click = Gtk.GestureClick.new()
            right_click.set_button(3)  # Right click
            right_click.connect("pressed", self._on_tag_right_click, tag)
            btn.add_controller(right_click)

            self.tag_buttons[tag_id] = btn
            self.tag_flowbox.append(btn)

    def _on_tag_clicked(self, tag_id: int):
        """Handle tag button click - toggle selection.

        Args:
            tag_id: ID of the clicked tag
        """
        # Toggle tag selection via manager
        self.tag_filter_manager.toggle_tag(tag_id)

        # Apply filter if tags are selected
        if self.tag_filter_manager.get_selected_tag_ids():
            self.apply_tag_filter()
        else:
            self.restore_filtered_view()

    def clear_tag_filter(self):
        """Clear all tag filters."""
        self.tag_filter_manager.clear_selection()
        self.restore_filtered_view()

    def apply_tag_filter(self):
        """Filter items by selected tags at UI level (no DB calls)."""
        # Determine which listbox to update
        current_tab = self.get_current_tab()
        if current_tab == "pasted":
            listbox = self.pasted_listbox
        else:
            listbox = self.copied_listbox

        # Apply filter via manager
        self.tag_filter_manager.apply_filter(listbox)

    def restore_filtered_view(self):
        """Restore normal unfiltered view by making all rows visible."""
        # Determine which listbox to update
        current_tab = self.get_current_tab()
        if current_tab == "pasted":
            listbox = self.pasted_listbox
        else:
            listbox = self.copied_listbox

        # Restore view via manager
        self.tag_filter_manager.restore_view(listbox)

    def reload_item_tags(self, item_id: int):
        """Reload tags for a specific clipboard item in both listboxes.

        Args:
            item_id: ID of the item to reload tags for
        """
        # Reload tags in copied listbox
        for row in self.copied_listbox:
            if hasattr(row, "item") and row.item.get("id") == item_id:
                if hasattr(row, "_load_item_tags"):
                    row._load_item_tags()
                break

        # Reload tags in pasted listbox
        for row in self.pasted_listbox:
            if hasattr(row, "item") and row.item.get("id") == item_id:
                if hasattr(row, "_load_item_tags"):
                    row._load_item_tags()
                break

    def get_tag_buttons(self) -> Dict[int, Gtk.Button]:
        """Get all tag button widgets.

        Returns:
            Dict[int, Gtk.Button]: Dictionary mapping tag IDs to button widgets
        """
        return self.tag_buttons

    def _on_tag_right_click(self, gesture, n_press, x, y, tag):
        """Handle right-click on a tag to show context menu.

        Args:
            gesture: The gesture that triggered this
            n_press: Number of presses
            x: X coordinate
            y: Y coordinate
            tag: The tag data dict
        """
        # Create a simple popover with buttons instead of menu
        popover = Gtk.Popover()
        popover.set_parent(gesture.get_widget())

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Rename button
        rename_btn = Gtk.Button(label="Rename")
        rename_btn.add_css_class("flat")
        rename_btn.set_halign(Gtk.Align.FILL)
        rename_btn.connect("clicked", lambda b, p=popover, t=tag: (self._on_rename_tag(t), p.popdown()))
        box.append(rename_btn)

        # Change color button
        color_btn = Gtk.Button(label="Change Color")
        color_btn.add_css_class("flat")
        color_btn.set_halign(Gtk.Align.FILL)
        color_btn.connect("clicked", lambda b, p=popover, t=tag: (self._on_change_tag_color(t), p.popdown()))
        box.append(color_btn)

        # Delete button
        delete_btn = Gtk.Button(label="Delete")
        delete_btn.add_css_class("flat")
        delete_btn.add_css_class("destructive-action")
        delete_btn.set_halign(Gtk.Align.FILL)
        delete_btn.connect("clicked", lambda b, p=popover, t=tag: (self._on_delete_tag(t), p.popdown()))
        box.append(delete_btn)

        popover.set_child(box)
        popover.popup()

    def _on_rename_tag(self, tag):
        """Handle rename tag action.

        Args:
            tag: The tag data dict
        """
        if not self.window:
            return

        # Use the window's tag dialog manager to show rename dialog
        if hasattr(self.window, 'tag_dialog_manager'):
            self.window.tag_dialog_manager.show_rename_dialog(tag)

    def _on_change_tag_color(self, tag):
        """Handle change tag color action.

        Args:
            tag: The tag data dict
        """
        if not self.window:
            return

        # Use the window's tag dialog manager to show color picker
        if hasattr(self.window, 'tag_dialog_manager'):
            self.window.tag_dialog_manager.show_color_picker_dialog(tag)

    def _on_delete_tag(self, tag):
        """Handle delete tag action with confirmation.

        Args:
            tag: The tag data dict
        """
        if not self.window:
            return

        # Show confirmation dialog
        dialog = Gtk.AlertDialog()
        dialog.set_message(f"Delete tag '{tag['name']}'?")
        dialog.set_detail("This tag will be removed from all tagged items and will no longer be available for use.")
        dialog.set_buttons(["Cancel", "Delete"])
        dialog.set_cancel_button(0)
        dialog.set_default_button(0)

        dialog.choose(self.window, None, self._on_delete_confirmed, tag)

    def _on_delete_confirmed(self, dialog, result, tag):
        """Handle delete confirmation response.

        Args:
            dialog: The alert dialog
            result: The async result
            tag: The tag data dict
        """
        try:
            button_index = dialog.choose_finish(result)
            if button_index == 1:  # Delete button
                # Use the window's tag dialog manager to delete the tag
                if self.window and hasattr(self.window, 'tag_dialog_manager'):
                    self.window.tag_dialog_manager.delete_tag(tag['id'])
        except Exception as e:
            logger.error(f"Error in delete confirmation: {e}")
