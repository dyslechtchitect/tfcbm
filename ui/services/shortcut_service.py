"""Shortcut recording and management service."""

import logging
from typing import Optional, Protocol

from ui.domain.keyboard import KeyboardShortcut
from ui.interfaces.keyboard_input import KeyEvent
from ui.interfaces.settings import ISettingsStore

logger = logging.getLogger("TFCBM.ShortcutService")


class ShortcutObserver(Protocol):
    """Observer protocol for shortcut recording events."""

    def on_shortcut_recorded(self, shortcut: KeyboardShortcut) -> None:
        """Called when a shortcut is successfully recorded."""
        pass

    def on_shortcut_applied(self, shortcut: KeyboardShortcut, success: bool) -> None:
        """Called after attempting to apply a shortcut."""
        pass


class ShortcutService:
    """Service for recording and managing keyboard shortcuts."""

    def __init__(self, settings_store: ISettingsStore):
        """
        Initialize the service.

        Args:
            settings_store: Storage backend for shortcuts
        """
        self.settings_store = settings_store
        self.is_recording = False
        self._observers: list[ShortcutObserver] = []

    def add_observer(self, observer: ShortcutObserver) -> None:
        """Add an observer for shortcut events."""
        if observer not in self._observers:
            self._observers.append(observer)

    def remove_observer(self, observer: ShortcutObserver) -> None:
        """Remove an observer."""
        if observer in self._observers:
            self._observers.remove(observer)

    def start_recording(self) -> None:
        """Start recording mode."""
        self.is_recording = True

    def stop_recording(self) -> None:
        """Stop recording mode."""
        self.is_recording = False

    def toggle_recording(self) -> bool:
        """
        Toggle recording mode.

        Returns:
            True if now recording, False otherwise
        """
        self.is_recording = not self.is_recording
        return self.is_recording

    def process_key_event(self, event: KeyEvent) -> Optional[KeyboardShortcut]:
        """
        Process a keyboard event during recording.

        Args:
            event: The keyboard event to process

        Returns:
            KeyboardShortcut if recorded successfully, None otherwise
        """
        if not self.is_recording:
            return None

        # Ignore modifier-only presses
        if event.is_modifier_only():
            return None

        # Create shortcut from event
        shortcut = KeyboardShortcut(modifiers=event.modifiers, key=event.keyname)

        # Stop recording
        self.stop_recording()

        # Notify observers
        for observer in self._observers:
            observer.on_shortcut_recorded(shortcut)

        return shortcut

    def get_current_shortcut(self) -> Optional[KeyboardShortcut]:
        """
        Get the current configured shortcut.

        Returns:
            Current shortcut or None
        """
        return self.settings_store.get_shortcut()

    def apply_shortcut(self, shortcut: KeyboardShortcut) -> bool:
        """
        Apply a shortcut to the settings store.

        Args:
            shortcut: Shortcut to apply

        Returns:
            True if successful, False otherwise
        """
        success = self.settings_store.set_shortcut(shortcut)

        # Notify observers
        for observer in self._observers:
            observer.on_shortcut_applied(shortcut, success)

        return success
