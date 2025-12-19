"""GTK-based keyboard event parser."""
from typing import List

from gi.repository import Gdk

from src.interfaces.keyboard_input import IKeyboardEventParser, KeyEvent


class GtkKeyboardEventParser(IKeyboardEventParser):
    """Parse GTK keyboard events into domain KeyEvent objects."""

    def parse_key_event(self, keyval: int, keycode: int, state: int) -> KeyEvent:
        """
        Parse a GTK keyboard event into a KeyEvent object.

        Args:
            keyval: GTK keyval
            keycode: Hardware keycode
            state: Modifier state mask

        Returns:
            KeyEvent object
        """
        keyname = Gdk.keyval_name(keyval)
        if not keyname:
            keyname = ""

        modifiers = self._extract_modifiers(state)

        return KeyEvent(keyname=keyname, modifiers=modifiers)

    def _extract_modifiers(self, state: int) -> List[str]:
        """
        Extract modifier key names from state mask.

        Args:
            state: GTK modifier state mask

        Returns:
            List of modifier names
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

        return modifiers
