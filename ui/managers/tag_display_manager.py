"""Tag Display Manager - Handles rendering and interaction with tag filter area."""

import logging
from typing import Callable, Dict, List, Set

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gtk

logger = logging.getLogger("TFCBM.TagDisplayManager")


class TagDisplayManager:
    """Manages tag display area including rendering, selection, and filtering."""

    def __init__(
        self,
        tag_flowbox: Gtk.FlowBox,
        tag_filter_manager,
        copied_listbox: Gtk.ListBox,
        pasted_listbox: Gtk.ListBox,
        get_current_tab: Callable[[], str],
        on_tag_drag_prepare: Callable,
        on_tag_drag_begin: Callable,
    ):
        """Initialize TagDisplayManager.

        Args:
            tag_flowbox: FlowBox widget for displaying tags
            tag_filter_manager: TagFilterManager instance for handling filtering
            copied_listbox: ListBox for copied items
            pasted_listbox: ListBox for pasted items
            get_current_tab: Callback to get current active tab
            on_tag_drag_prepare: Callback for tag drag prepare event
            on_tag_drag_begin: Callback for tag drag begin event
        """
        self.tag_flowbox = tag_flowbox
        self.tag_filter_manager = tag_filter_manager
        self.copied_listbox = copied_listbox
        self.pasted_listbox = pasted_listbox
        self.get_current_tab = get_current_tab
        self.on_tag_drag_prepare = on_tag_drag_prepare
        self.on_tag_drag_begin = on_tag_drag_begin

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

        # Add tag buttons
        for tag in user_tags:
            tag_id = tag.get("id")
            tag_name = tag.get("name", "")
            tag_color = tag.get("color", "#9a9996")
            is_selected = tag_id in self.tag_filter_manager.get_selected_tag_ids()

            # Create button for tag
            btn = Gtk.Button.new_with_label(tag_name)
            btn.add_css_class("pill")

            # Apply color styling - selected tags colored, unselected greyed out
            css_provider = Gtk.CssProvider()
            if is_selected:
                css_data = f"button.pill {{ background-color: alpha({tag_color}, 0.25); color: {tag_color}; font-size: 9pt; font-weight: normal; padding: 2px 8px; min-height: 20px; border: 1px solid alpha({tag_color}, 0.4); border-radius: 2px; }}"
            else:
                # Unselected: greyed out
                css_data = "button.pill { background-color: alpha(#666666, 0.08); color: alpha(#666666, 0.5); font-size: 9pt; font-weight: normal; padding: 2px 8px; min-height: 20px; border: 1px solid alpha(#666666, 0.2); border-radius: 2px; }"
            css_provider.load_from_data(css_data.encode())
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
