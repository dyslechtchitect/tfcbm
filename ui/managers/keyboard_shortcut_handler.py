"""Handles keyboard shortcuts and keyboard-triggered actions."""

import logging
import shutil
import subprocess
from typing import Any

import gi
from gi.repository import Gdk, GLib, Gtk

gi.require_version("Gtk", "4.0")

logger = logging.getLogger("TFCBM.KeyboardShortcutHandler")


class KeyboardShortcutHandler:
    """Manages keyboard shortcuts and keyboard-activated behaviors."""

    def __init__(
        self,
        window: Any,
        search_entry: Gtk.SearchEntry,
        copied_listbox: Gtk.ListBox,
    ):
        """Initialize KeyboardShortcutHandler.

        Args:
            window: The main window instance
            search_entry: The search entry widget to auto-focus
            copied_listbox: The listbox for the copied tab (for first item focus)
        """
        self.window = window
        self.search_entry = search_entry
        self.copied_listbox = copied_listbox

        # Track if window was activated via keyboard shortcut (Ctrl+`)
        self.activated_via_keyboard = False

        # Set up keyboard event controller
        self._setup_keyboard_controller()

    def _setup_keyboard_controller(self) -> None:
        """Set up the keyboard event controller."""
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self._on_key_pressed)
        self.window.add_controller(key_controller)

    def focus_first_item(self) -> bool:
        """Focus the first item in the copied tab list when opened via keyboard shortcut.

        Returns:
            False to prevent GLib timeout from repeating
        """
        try:
            # Get the first row from the copied listbox (Copied tab)
            first_row = self.copied_listbox.get_row_at_index(0)
            if first_row:
                # Set focus to the first row
                first_row.grab_focus()
                logger.info("[KEYBOARD] Auto-focused first item in list")
                return False  # Don't repeat
            else:
                logger.warning("[KEYBOARD] No items to focus")
                return False
        except Exception as e:
            logger.error(f"[KEYBOARD] Error focusing first item: {e}")
            return False

    def _on_key_pressed(
        self, controller: Gtk.EventControllerKey, keyval: int, keycode: int, state: int
    ) -> bool:
        """Handle keyboard shortcuts: Return/Space to copy item, alphanumeric to focus search.

        Args:
            controller: The event controller
            keyval: The key value
            keycode: The key code
            state: The modifier state

        Returns:
            True if event was handled, False to propagate
        """
        # Get the currently focused widget
        focused_widget = self.window.get_focus()

        # Feature 1: Auto-focus search bar on alphanumeric keypress
        # Check if this is an alphanumeric key (a-z, A-Z, 0-9)
        is_alphanumeric = False
        if (
            Gdk.KEY_a <= keyval <= Gdk.KEY_z
            or Gdk.KEY_A <= keyval <= Gdk.KEY_Z
            or Gdk.KEY_0 <= keyval <= Gdk.KEY_9
        ):
            is_alphanumeric = True

        # If alphanumeric and search bar is NOT focused, focus it and let the key be typed
        if is_alphanumeric:
            if focused_widget != self.search_entry:
                logger.info(
                    "[KEYBOARD] Auto-focusing search bar on alphanumeric key"
                )
                self.search_entry.grab_focus()
                # Return False to let the key event propagate to the search entry
                return False

        # Handle Return/Space key press to copy item
        if keyval not in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_space):
            return False  # Let other handlers process this key

        if not focused_widget:
            return False

        # Import here to avoid circular imports
        from ui.rows.clipboard_item_row import ClipboardItemRow

        # Find the ClipboardItemRow - it might be the focused widget or a parent
        row = focused_widget
        max_depth = 10  # Prevent infinite loop
        while row and max_depth > 0:
            if isinstance(row, ClipboardItemRow):
                # Found the row! Copy it
                logger.info(f"[KEYBOARD] Copying item {row.item.get('id')} via keyboard")
                # Note: _on_row_clicked already handles the paste simulation
                # when activated_via_keyboard is True, so we don't need to do it here
                row._on_row_clicked(row)
                return True  # Event handled

            # Move up the widget hierarchy
            row = row.get_parent()
            max_depth -= 1

        return False  # Not handled
