"""Integration tests for settings storage."""
import pytest

from tests.helpers import IntegrationTestContext, create_shortcut


class TestSettingsStore:
    """Test settings store functionality."""

    def setup_method(self):
        """Set up test context before each test."""
        self.context = IntegrationTestContext()

    def test_save_and_retrieve_shortcut(self):
        """
        GIVEN: A settings store
        WHEN: A shortcut is saved
        THEN: It can be retrieved
        """
        # GIVEN
        store = self.context.settings_store
        shortcut = create_shortcut(["Ctrl", "Shift"], "k")

        # WHEN
        success = store.set_shortcut(shortcut)
        retrieved = store.get_shortcut()

        # THEN
        assert success is True
        assert retrieved is not None
        assert retrieved.key == "k"
        assert "Ctrl" in retrieved.modifiers
        assert "Shift" in retrieved.modifiers

    def test_retrieve_none_when_not_configured(self):
        """
        GIVEN: A settings store with no shortcut configured
        WHEN: Shortcut is retrieved
        THEN: None should be returned
        """
        # GIVEN
        store = self.context.settings_store

        # WHEN
        retrieved = store.get_shortcut()

        # THEN
        assert retrieved is None

    def test_overwrite_existing_shortcut(self):
        """
        GIVEN: A settings store with a configured shortcut
        WHEN: A new shortcut is saved
        THEN: The new shortcut should be retrieved
        """
        # GIVEN
        store = self.context.settings_store
        old_shortcut = create_shortcut(["Ctrl"], "a")
        store.set_shortcut(old_shortcut)

        # WHEN
        new_shortcut = create_shortcut(["Alt"], "b")
        store.set_shortcut(new_shortcut)
        retrieved = store.get_shortcut()

        # THEN
        assert retrieved is not None
        assert retrieved.key == "b"
        assert "Alt" in retrieved.modifiers
        assert "Ctrl" not in retrieved.modifiers

    def test_save_shortcut_without_modifiers(self):
        """
        GIVEN: A settings store
        WHEN: A shortcut without modifiers is saved
        THEN: It can be retrieved correctly
        """
        # GIVEN
        store = self.context.settings_store
        shortcut = create_shortcut([], "F1")

        # WHEN
        success = store.set_shortcut(shortcut)
        retrieved = store.get_shortcut()

        # THEN
        assert success is True
        assert retrieved is not None
        assert retrieved.key == "F1"
        assert len(retrieved.modifiers) == 0

    def test_save_shortcut_with_multiple_modifiers(self):
        """
        GIVEN: A settings store
        WHEN: A shortcut with multiple modifiers is saved
        THEN: All modifiers are preserved
        """
        # GIVEN
        store = self.context.settings_store
        shortcut = create_shortcut(["Ctrl", "Shift", "Alt"], "F12")

        # WHEN
        success = store.set_shortcut(shortcut)
        retrieved = store.get_shortcut()

        # THEN
        assert success is True
        assert retrieved is not None
        assert retrieved.key == "F12"
        assert "Ctrl" in retrieved.modifiers
        assert "Shift" in retrieved.modifiers
        assert "Alt" in retrieved.modifiers


class TestShortcutService:
    """Test shortcut service integration with settings store."""

    def setup_method(self):
        """Set up test context before each test."""
        self.context = IntegrationTestContext()

    def test_get_current_shortcut(self):
        """
        GIVEN: A configured shortcut in settings
        WHEN: Current shortcut is requested
        THEN: The configured shortcut is returned
        """
        # GIVEN
        shortcut = create_shortcut(["Ctrl", "Shift"], "k")
        self.context.given_shortcut_is_configured(shortcut)
        service = self.context.shortcut_service

        # WHEN
        current = service.get_current_shortcut()

        # THEN
        assert current is not None
        assert current.key == "k"
        assert "Ctrl" in current.modifiers
        assert "Shift" in current.modifiers

    def test_apply_shortcut_saves_to_store(self):
        """
        GIVEN: A shortcut service
        WHEN: A shortcut is applied
        THEN: It should be saved to the settings store
        """
        # GIVEN
        service = self.context.shortcut_service
        store = self.context.settings_store
        shortcut = create_shortcut(["Alt"], "F1")

        # WHEN
        success = service.apply_shortcut(shortcut)

        # THEN
        assert success is True
        retrieved = store.get_shortcut()
        assert retrieved is not None
        assert retrieved.key == "F1"
        assert "Alt" in retrieved.modifiers
