"""GTK keyboard event parser implementation."""

from typing import List

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk

from ui.interfaces.keyboard_input import IKeyboardEventParser, KeyEvent


class GtkKeyboardParser(IKeyboardEventParser):
    """Parse GTK keyboard events into KeyEvent objects."""

    def parse_key_event(self, keyval: int, keycode: int, state: int) -> KeyEvent:
        """
        Parse a GTK key event into a KeyEvent.

        Args:
            keyval: GTK keyval
            keycode: Hardware keycode
            state: Modifier state (Gdk.ModifierType)

        Returns:
            Parsed KeyEvent
        """
        # Get key name
        keyname = Gdk.keyval_name(keyval)
        if keyname is None:
            keyname = f"keycode_{keycode}"

        # Parse modifiers from state
        modifiers = self._parse_modifiers(state)

        return KeyEvent(keyname=keyname, modifiers=modifiers)

    def _parse_modifiers(self, state: int) -> List[str]:
        """
        Parse modifier state into list of modifier names.

        Args:
            state: Gdk.ModifierType flags

        Returns:
            List of modifier names (e.g., ["Ctrl", "Shift"])
        """
        modifiers = []

        if state & Gdk.ModifierType.CONTROL_MASK:
            modifiers.append("Ctrl")
        if state & Gdk.ModifierType.SHIFT_MASK:
            modifiers.append("Shift")
        if state & Gdk.ModifierType.ALT_MASK:
            modifiers.append("Alt")
        if state & Gdk.ModifierType.SUPER_MASK:
            modifiers.append("Super")
        if state & Gdk.ModifierType.META_MASK:
            modifiers.append("Meta")

        return modifiers
