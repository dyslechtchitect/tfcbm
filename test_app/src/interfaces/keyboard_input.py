"""Keyboard input interface."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class KeyEvent:
    """Value object representing a keyboard event."""

    keyname: str
    modifiers: List[str]

    def is_modifier_only(self) -> bool:
        """Check if this is a modifier-only key press."""
        from src.domain.keyboard import MODIFIER_ONLY_KEYS
        return self.keyname in MODIFIER_ONLY_KEYS


class IKeyboardEventParser(ABC):
    """Abstract interface for parsing keyboard events."""

    @abstractmethod
    def parse_key_event(self, keyval: int, keycode: int, state: int) -> KeyEvent:
        """
        Parse a keyboard event into a KeyEvent object.

        Args:
            keyval: GTK keyval
            keycode: Hardware keycode
            state: Modifier state mask

        Returns:
            KeyEvent object
        """
        pass
