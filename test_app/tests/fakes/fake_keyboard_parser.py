"""Fake keyboard event parser for testing."""
from typing import Dict, List

from src.interfaces.keyboard_input import IKeyboardEventParser, KeyEvent


class FakeKeyboardEventParser(IKeyboardEventParser):
    """Fake keyboard parser that returns predefined events."""

    def __init__(self):
        """Initialize the fake parser."""
        self.call_count = 0
        self._event_map: Dict[tuple, KeyEvent] = {}

    def parse_key_event(self, keyval: int, keycode: int, state: int) -> KeyEvent:
        """
        Parse a keyboard event.

        Args:
            keyval: GTK keyval
            keycode: Hardware keycode
            state: Modifier state mask

        Returns:
            KeyEvent object
        """
        self.call_count += 1
        key = (keyval, keycode, state)

        if key in self._event_map:
            return self._event_map[key]

        # Default: return simple event
        return KeyEvent(keyname=f"key_{keyval}", modifiers=[])

    def configure_event(
        self,
        keyval: int,
        keycode: int,
        state: int,
        keyname: str,
        modifiers: List[str]
    ) -> None:
        """
        Configure the fake to return specific event for given inputs.

        Args:
            keyval: GTK keyval
            keycode: Hardware keycode
            state: Modifier state
            keyname: Key name to return
            modifiers: Modifiers to return
        """
        key = (keyval, keycode, state)
        self._event_map[key] = KeyEvent(keyname=keyname, modifiers=modifiers)

    def reset(self) -> None:
        """Reset the fake to initial state."""
        self.call_count = 0
        self._event_map.clear()
