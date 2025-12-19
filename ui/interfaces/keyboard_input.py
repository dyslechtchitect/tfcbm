"""Keyboard input interfaces."""

from dataclasses import dataclass
from typing import List, Protocol

from ui.domain.keyboard import MODIFIER_ONLY_KEYS


@dataclass
class KeyEvent:
    """Represents a keyboard event."""

    keyname: str
    modifiers: List[str]

    def is_modifier_only(self) -> bool:
        """Check if this is just a modifier key press."""
        return self.keyname in MODIFIER_ONLY_KEYS


class IKeyboardEventParser(Protocol):
    """Interface for parsing GTK keyboard events."""

    def parse_key_event(self, keyval: int, keycode: int, state: int) -> KeyEvent:
        """
        Parse a GTK key event into a KeyEvent.

        Args:
            keyval: GTK keyval
            keycode: Hardware keycode
            state: Modifier state

        Returns:
            Parsed KeyEvent
        """
        pass
