"""Fake settings store for testing."""
from typing import Optional

from src.domain.keyboard import KeyboardShortcut
from src.interfaces.settings import ISettingsStore


class FakeSettingsStore(ISettingsStore):
    """In-memory fake settings store for testing."""

    def __init__(self):
        """Initialize the fake store."""
        self._shortcut: Optional[KeyboardShortcut] = None
        self.get_call_count = 0
        self.set_call_count = 0
        self.should_fail_get = False
        self.should_fail_set = False

    def get_shortcut(self) -> Optional[KeyboardShortcut]:
        """
        Read the current keyboard shortcut.

        Returns:
            KeyboardShortcut if configured, None otherwise
        """
        self.get_call_count += 1
        if self.should_fail_get:
            return None
        return self._shortcut

    def set_shortcut(self, shortcut: KeyboardShortcut) -> bool:
        """
        Write a keyboard shortcut.

        Args:
            shortcut: The shortcut to save

        Returns:
            True if successful, False otherwise
        """
        self.set_call_count += 1
        if self.should_fail_set:
            return False
        self._shortcut = shortcut
        return True

    def reset(self) -> None:
        """Reset the fake to initial state."""
        self._shortcut = None
        self.get_call_count = 0
        self.set_call_count = 0
        self.should_fail_get = False
        self.should_fail_set = False
