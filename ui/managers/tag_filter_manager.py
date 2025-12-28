"""Manages tag-based filtering of clipboard items."""

import logging
from typing import Any, Callable, List

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk

logger = logging.getLogger("TFCBM.TagFilterManager")


class TagFilterManager:
    """Manages tag-based filtering and selection state."""

    # System tag ID to item type mapping
    SYSTEM_TAG_TYPE_MAP = {
        "system_text": ["text"],
        "system_image": [
            "image/generic",
            "image/file",
            "image/web",
            "image/screenshot",
        ],
        "system_screenshot": ["image/screenshot"],
        "system_url": ["url"],
    }

    def __init__(
        self,
        on_tag_display_refresh: Callable[[], None],
        on_notification: Callable[[str], None],
    ):
        """Initialize TagFilterManager.

        Args:
            on_tag_display_refresh: Callback to refresh tag display UI
            on_notification: Callback to show notification message
        """
        self.on_tag_display_refresh = on_tag_display_refresh
        self.on_notification = on_notification

        # Filter state
        self.selected_tag_ids: List[str] = []
        self.filter_active = False

    def get_selected_tag_ids(self) -> List[str]:
        """Get currently selected tag IDs.

        Returns:
            List[str]: List of selected tag IDs
        """
        return self.selected_tag_ids.copy()

    def is_filter_active(self) -> bool:
        """Check if tag filter is currently active.

        Returns:
            bool: True if filter is active
        """
        return self.filter_active

    def toggle_tag(self, tag_id: str) -> None:
        """Toggle tag selection.

        Args:
            tag_id: Tag ID to toggle
        """
        if tag_id in self.selected_tag_ids:
            self.selected_tag_ids.remove(tag_id)
        else:
            self.selected_tag_ids.append(tag_id)

        # Refresh display to update button styles
        self.on_tag_display_refresh()

    def clear_selection(self) -> None:
        """Clear all selected tags."""
        self.selected_tag_ids = []
        self.filter_active = False
        self.on_tag_display_refresh()

    def apply_filter(
        self, listbox: Gtk.ListBox, show_filtered_count: bool = True
    ) -> int:
        """Apply tag filter to listbox items.

        Args:
            listbox: The listbox to filter
            show_filtered_count: Whether to show notification with count

        Returns:
            int: Number of visible items after filtering
        """
        if not self.selected_tag_ids:
            self.restore_view(listbox)
            return 0

        logger.info(f"Applying tag filter: {self.selected_tag_ids}")

        # Get user-defined tag IDs (non-system tags)
        user_tag_ids = [
            tag_id
            for tag_id in self.selected_tag_ids
            if not str(tag_id).startswith("system_")
        ]

        # Get allowed types from system tags
        allowed_types = []
        for tag_id in self.selected_tag_ids:
            if tag_id in self.SYSTEM_TAG_TYPE_MAP:
                allowed_types.extend(self.SYSTEM_TAG_TYPE_MAP[tag_id])

        # Filter rows by showing/hiding them based on tags
        visible_count = 0
        i = 0
        while True:
            row = listbox.get_row_at_index(i)
            if not row:
                break

            if hasattr(row, "item"):
                item = row.item
                item_type = item.get("type", "")
                item_tags = item.get("tags", [])

                # Extract tag IDs from item tags
                item_tag_ids = [
                    tag.get("id") for tag in item_tags if isinstance(tag, dict)
                ]

                # Check if item matches filter
                matches = False

                # If we have system tag filters, check type match
                if allowed_types:
                    if item_type in allowed_types:
                        # If we also have user tags, check if item has those tags
                        if user_tag_ids:
                            # Item must have at least one of the selected user tags
                            if any(
                                tag_id in item_tag_ids for tag_id in user_tag_ids
                            ):
                                matches = True
                        else:
                            # No user tags, just type match is enough
                            matches = True

                # If we only have user tag filters (no system tags)
                elif user_tag_ids:
                    if any(tag_id in item_tag_ids for tag_id in user_tag_ids):
                        matches = True

                # Show/hide row based on match
                row.set_visible(matches)
                if matches:
                    visible_count += 1

            i += 1

        self.filter_active = True

        if show_filtered_count:
            self.on_notification(f"Showing {visible_count} filtered items")

        return visible_count

    def restore_view(self, listbox: Gtk.ListBox) -> None:
        """Restore normal unfiltered view by making all rows visible.

        Args:
            listbox: The listbox to restore
        """
        if not self.filter_active:
            return

        self.filter_active = False

        # Show all rows again
        i = 0
        while True:
            row = listbox.get_row_at_index(i)
            if not row:
                break
            row.set_visible(True)
            i += 1
