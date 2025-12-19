"""Integration tests for shortcut recording functionality."""
import pytest

from src.domain.keyboard import KeyboardShortcut
from tests.helpers import IntegrationTestContext, create_shortcut


class TestShortcutRecording:
    """Test shortcut recording workflow."""

    def setup_method(self):
        """Set up test context before each test."""
        self.context = IntegrationTestContext()

    def test_start_recording_mode(self):
        """
        GIVEN: A shortcut service
        WHEN: Recording mode is started
        THEN: Service should be in recording mode
        """
        # GIVEN
        service = self.context.shortcut_service

        # WHEN
        service.start_recording()

        # THEN
        assert service.is_recording is True

    def test_stop_recording_mode(self):
        """
        GIVEN: A shortcut service in recording mode
        WHEN: Recording mode is stopped
        THEN: Service should not be in recording mode
        """
        # GIVEN
        service = self.context.shortcut_service
        service.start_recording()

        # WHEN
        service.stop_recording()

        # THEN
        assert service.is_recording is False

    def test_toggle_recording_mode(self):
        """
        GIVEN: A shortcut service not in recording mode
        WHEN: Recording mode is toggled
        THEN: Service should be in recording mode
        """
        # GIVEN
        service = self.context.shortcut_service
        assert service.is_recording is False

        # WHEN
        result = service.toggle_recording()

        # THEN
        assert result is True
        assert service.is_recording is True

    def test_record_shortcut_with_modifiers(self):
        """
        GIVEN: Service in recording mode
        WHEN: A key with modifiers is pressed
        THEN: Shortcut should be recorded and recording should stop
        """
        # GIVEN
        service = self.context.shortcut_service
        service.start_recording()
        self.context.given_fake_keyboard_event(
            keyval=107,  # 'k'
            keycode=45,
            state=5,  # Ctrl+Shift
            keyname="k",
            modifiers=["Ctrl", "Shift"]
        )

        # WHEN
        shortcut = self.context.when_key_event_occurs(
            keyval=107,
            keycode=45,
            state=5
        )

        # THEN
        assert shortcut is not None
        assert shortcut.key == "k"
        assert "Ctrl" in shortcut.modifiers
        assert "Shift" in shortcut.modifiers
        assert service.is_recording is False

    def test_record_shortcut_without_modifiers(self):
        """
        GIVEN: Service in recording mode
        WHEN: A key without modifiers is pressed
        THEN: Shortcut should be recorded with empty modifiers
        """
        # GIVEN
        service = self.context.shortcut_service
        service.start_recording()
        self.context.given_fake_keyboard_event(
            keyval=65,  # 'a'
            keycode=38,
            state=0,
            keyname="a",
            modifiers=[]
        )

        # WHEN
        shortcut = self.context.when_key_event_occurs(
            keyval=65,
            keycode=38,
            state=0
        )

        # THEN
        assert shortcut is not None
        assert shortcut.key == "a"
        assert len(shortcut.modifiers) == 0

    def test_ignore_modifier_only_keys(self):
        """
        GIVEN: Service in recording mode
        WHEN: Only a modifier key is pressed
        THEN: No shortcut should be recorded
        """
        # GIVEN
        service = self.context.shortcut_service
        service.start_recording()
        self.context.given_fake_keyboard_event(
            keyval=65507,  # Control_L
            keycode=37,
            state=4,
            keyname="Control_L",
            modifiers=["Ctrl"]
        )

        # WHEN
        shortcut = self.context.when_key_event_occurs(
            keyval=65507,
            keycode=37,
            state=4
        )

        # THEN
        assert shortcut is None
        assert service.is_recording is True  # Still recording

    def test_ignore_key_events_when_not_recording(self):
        """
        GIVEN: Service NOT in recording mode
        WHEN: A key is pressed
        THEN: No shortcut should be recorded
        """
        # GIVEN
        service = self.context.shortcut_service
        assert service.is_recording is False
        self.context.given_fake_keyboard_event(
            keyval=107,
            keycode=45,
            state=5,
            keyname="k",
            modifiers=["Ctrl", "Shift"]
        )

        # WHEN
        shortcut = self.context.when_key_event_occurs(
            keyval=107,
            keycode=45,
            state=5
        )

        # THEN
        assert shortcut is None


class TestShortcutObserver:
    """Test shortcut observer notifications."""

    def setup_method(self):
        """Set up test context before each test."""
        self.context = IntegrationTestContext()
        self.recorded_shortcut = None
        self.applied_shortcut = None
        self.applied_success = None

    def on_shortcut_recorded(self, shortcut: KeyboardShortcut):
        """Observer callback for recorded shortcut."""
        self.recorded_shortcut = shortcut

    def on_shortcut_applied(self, shortcut: KeyboardShortcut, success: bool):
        """Observer callback for applied shortcut."""
        self.applied_shortcut = shortcut
        self.applied_success = success

    def test_observer_notified_on_recording(self):
        """
        GIVEN: Service with registered observer
        WHEN: A shortcut is recorded
        THEN: Observer should be notified
        """
        # GIVEN
        service = self.context.shortcut_service
        service.add_observer(self)
        service.start_recording()
        self.context.given_fake_keyboard_event(
            keyval=107,
            keycode=45,
            state=5,
            keyname="k",
            modifiers=["Ctrl", "Shift"]
        )

        # WHEN
        self.context.when_key_event_occurs(107, 45, 5)

        # THEN
        assert self.recorded_shortcut is not None
        assert self.recorded_shortcut.key == "k"

    def test_observer_notified_on_apply_success(self):
        """
        GIVEN: Service with registered observer
        WHEN: A shortcut is successfully applied
        THEN: Observer should be notified with success=True
        """
        # GIVEN
        service = self.context.shortcut_service
        service.add_observer(self)
        shortcut = create_shortcut(["Ctrl", "Shift"], "k")

        # WHEN
        service.apply_shortcut(shortcut)

        # THEN
        assert self.applied_shortcut is not None
        assert self.applied_shortcut == shortcut
        assert self.applied_success is True

    def test_observer_notified_on_apply_failure(self):
        """
        GIVEN: Service with failing settings store
        WHEN: A shortcut fails to apply
        THEN: Observer should be notified with success=False
        """
        # GIVEN
        self.context.settings_store.should_fail_set = True
        service = self.context.shortcut_service
        service.add_observer(self)
        shortcut = create_shortcut(["Ctrl", "Shift"], "k")

        # WHEN
        service.apply_shortcut(shortcut)

        # THEN
        assert self.applied_shortcut is not None
        assert self.applied_success is False
