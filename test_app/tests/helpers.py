"""Test helpers and utilities."""
from typing import Optional

from src.application.activation_tracker import ActivationTracker
from src.application.shortcut_service import ShortcutService
from src.config import ApplicationConfig
from src.domain.keyboard import KeyboardShortcut
from src.interfaces.keyboard_input import IKeyboardEventParser, KeyEvent
from tests.fakes.fake_keyboard_parser import FakeKeyboardEventParser
from tests.fakes.fake_settings_store import FakeSettingsStore


class IntegrationTestContext:
    """Test context with all dependencies configured."""

    def __init__(
        self,
        use_real_keyboard_parser: bool = False,
        use_real_settings_store: bool = False
    ):
        """
        Initialize test context.

        Args:
            use_real_keyboard_parser: If True, use real GTK keyboard parser
            use_real_settings_store: If True, use real GSettings store
        """
        # Configuration
        self.config = ApplicationConfig()

        # Infrastructure (use fakes by default)
        if use_real_settings_store:
            from src.infrastructure.gsettings_store import GSettingsStore
            self.settings_store = GSettingsStore(self.config)
        else:
            self.settings_store = FakeSettingsStore()

        if use_real_keyboard_parser:
            from src.infrastructure.gtk_keyboard_parser import GtkKeyboardEventParser
            self.keyboard_parser: IKeyboardEventParser = GtkKeyboardEventParser()
        else:
            self.keyboard_parser = FakeKeyboardEventParser()

        # Application services
        self.shortcut_service = ShortcutService(self.settings_store)
        self.activation_tracker = ActivationTracker()

    def given_shortcut_is_configured(self, shortcut: KeyboardShortcut) -> None:
        """Configure a shortcut in the settings store."""
        if isinstance(self.settings_store, FakeSettingsStore):
            self.settings_store.set_shortcut(shortcut)
        else:
            self.settings_store.set_shortcut(shortcut)

    def given_fake_keyboard_event(
        self,
        keyval: int,
        keycode: int,
        state: int,
        keyname: str,
        modifiers: list[str]
    ) -> None:
        """Configure the fake keyboard parser to return specific event."""
        if isinstance(self.keyboard_parser, FakeKeyboardEventParser):
            self.keyboard_parser.configure_event(
                keyval, keycode, state, keyname, modifiers
            )

    def when_key_event_occurs(
        self,
        keyval: int,
        keycode: int,
        state: int
    ) -> Optional[KeyboardShortcut]:
        """Simulate a key event being processed."""
        event = self.keyboard_parser.parse_key_event(keyval, keycode, state)
        return self.shortcut_service.process_key_event(event)

    def reset(self) -> None:
        """Reset all test state."""
        if isinstance(self.settings_store, FakeSettingsStore):
            self.settings_store.reset()
        if isinstance(self.keyboard_parser, FakeKeyboardEventParser):
            self.keyboard_parser.reset()

        # Reset services
        self.shortcut_service = ShortcutService(self.settings_store)
        self.activation_tracker = ActivationTracker()


def create_shortcut(modifiers: list[str], key: str) -> KeyboardShortcut:
    """
    Helper to create a keyboard shortcut.

    Args:
        modifiers: List of modifier names (e.g., ["Ctrl", "Shift"])
        key: Key name (e.g., "k")

    Returns:
        KeyboardShortcut instance
    """
    return KeyboardShortcut(modifiers=modifiers, key=key)


def create_key_event(keyname: str, modifiers: list[str]) -> KeyEvent:
    """
    Helper to create a keyboard event.

    Args:
        keyname: Key name
        modifiers: List of modifier names

    Returns:
        KeyEvent instance
    """
    return KeyEvent(keyname=keyname, modifiers=modifiers)
