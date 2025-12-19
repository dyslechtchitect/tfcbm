"""Settings storage interface."""
from abc import ABC, abstractmethod
from typing import Optional

from src.domain.keyboard import KeyboardShortcut


class ISettingsStore(ABC):
    """Abstract interface for reading and writing settings."""

    @abstractmethod
    def get_shortcut(self) -> Optional[KeyboardShortcut]:
        """
        Read the current keyboard shortcut from settings.

        Returns:
            KeyboardShortcut if configured, None otherwise
        """
        pass

    @abstractmethod
    def set_shortcut(self, shortcut: KeyboardShortcut) -> bool:
        """
        Write a keyboard shortcut to settings.

        Args:
            shortcut: The shortcut to save

        Returns:
            True if successful, False otherwise
        """
        pass
