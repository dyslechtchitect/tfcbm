"""Integration tests for keyboard shortcut domain logic."""
import pytest

from src.domain.keyboard import MODIFIER_ONLY_KEYS, KeyboardShortcut


class TestKeyboardShortcutValueObject:
    """Test KeyboardShortcut value object."""

    def test_to_gtk_string_with_modifiers(self):
        """
        GIVEN: A shortcut with modifiers
        WHEN: Converted to GTK string
        THEN: Should format as <Mod1><Mod2>key
        """
        # GIVEN
        shortcut = KeyboardShortcut(modifiers=["Ctrl", "Shift"], key="k")

        # WHEN
        gtk_string = shortcut.to_gtk_string()

        # THEN
        assert gtk_string == "<Ctrl><Shift>k"

    def test_to_gtk_string_without_modifiers(self):
        """
        GIVEN: A shortcut without modifiers
        WHEN: Converted to GTK string
        THEN: Should return just the key
        """
        # GIVEN
        shortcut = KeyboardShortcut(modifiers=[], key="F1")

        # WHEN
        gtk_string = shortcut.to_gtk_string()

        # THEN
        assert gtk_string == "F1"

    def test_to_display_string_with_modifiers(self):
        """
        GIVEN: A shortcut with modifiers
        WHEN: Converted to display string
        THEN: Should format as Mod1+Mod2+Key
        """
        # GIVEN
        shortcut = KeyboardShortcut(modifiers=["Ctrl", "Shift"], key="k")

        # WHEN
        display = shortcut.to_display_string()

        # THEN
        assert display == "Ctrl+Shift+k"

    def test_to_display_string_without_modifiers(self):
        """
        GIVEN: A shortcut without modifiers
        WHEN: Converted to display string
        THEN: Should return just the key
        """
        # GIVEN
        shortcut = KeyboardShortcut(modifiers=[], key="F1")

        # WHEN
        display = shortcut.to_display_string()

        # THEN
        assert display == "F1"

    def test_from_gtk_string_with_modifiers(self):
        """
        GIVEN: A GTK-formatted shortcut string
        WHEN: Parsed into KeyboardShortcut
        THEN: Should extract modifiers and key
        """
        # GIVEN
        gtk_string = "<Ctrl><Shift>k"

        # WHEN
        shortcut = KeyboardShortcut.from_gtk_string(gtk_string)

        # THEN
        assert shortcut.key == "k"
        assert "Ctrl" in shortcut.modifiers
        assert "Shift" in shortcut.modifiers

    def test_from_gtk_string_control_variant(self):
        """
        GIVEN: A GTK string with <Control> instead of <Ctrl>
        WHEN: Parsed into KeyboardShortcut
        THEN: Should normalize to Ctrl
        """
        # GIVEN
        gtk_string = "<Control><Shift>k"

        # WHEN
        shortcut = KeyboardShortcut.from_gtk_string(gtk_string)

        # THEN
        assert "Ctrl" in shortcut.modifiers

    def test_from_gtk_string_without_modifiers(self):
        """
        GIVEN: A GTK string with no modifiers
        WHEN: Parsed into KeyboardShortcut
        THEN: Should have empty modifiers
        """
        # GIVEN
        gtk_string = "F1"

        # WHEN
        shortcut = KeyboardShortcut.from_gtk_string(gtk_string)

        # THEN
        assert shortcut.key == "F1"
        assert len(shortcut.modifiers) == 0

    def test_from_gsettings_array(self):
        """
        GIVEN: A GSettings array format string
        WHEN: Parsed into KeyboardShortcut
        THEN: Should extract shortcut correctly
        """
        # GIVEN
        gsettings_output = "['<Control><Shift>k']"

        # WHEN
        shortcut = KeyboardShortcut.from_gsettings_array(gsettings_output)

        # THEN
        assert shortcut.key == "k"
        assert "Ctrl" in shortcut.modifiers
        assert "Shift" in shortcut.modifiers

    def test_from_gsettings_array_empty_raises_error(self):
        """
        GIVEN: An empty GSettings array
        WHEN: Parsed into KeyboardShortcut
        THEN: Should raise ValueError
        """
        # GIVEN
        gsettings_output = "[]"

        # WHEN / THEN
        with pytest.raises(ValueError):
            KeyboardShortcut.from_gsettings_array(gsettings_output)

    def test_roundtrip_gtk_string(self):
        """
        GIVEN: A KeyboardShortcut
        WHEN: Converted to GTK string and back
        THEN: Should produce equivalent shortcut
        """
        # GIVEN
        original = KeyboardShortcut(modifiers=["Ctrl", "Alt"], key="F12")

        # WHEN
        gtk_string = original.to_gtk_string()
        parsed = KeyboardShortcut.from_gtk_string(gtk_string)

        # THEN
        assert parsed.key == original.key
        assert set(parsed.modifiers) == set(original.modifiers)

    def test_immutability(self):
        """
        GIVEN: A KeyboardShortcut value object
        WHEN: Attempting to modify it
        THEN: Should raise an error (frozen dataclass)
        """
        # GIVEN
        shortcut = KeyboardShortcut(modifiers=["Ctrl"], key="k")

        # WHEN / THEN
        with pytest.raises(AttributeError):
            shortcut.key = "j"  # type: ignore


class TestModifierOnlyKeys:
    """Test modifier-only key detection."""

    def test_modifier_only_keys_are_defined(self):
        """
        GIVEN: MODIFIER_ONLY_KEYS constant
        WHEN: Checked
        THEN: Should contain common modifier key names
        """
        # GIVEN / WHEN / THEN
        assert "Control_L" in MODIFIER_ONLY_KEYS
        assert "Control_R" in MODIFIER_ONLY_KEYS
        assert "Shift_L" in MODIFIER_ONLY_KEYS
        assert "Shift_R" in MODIFIER_ONLY_KEYS
        assert "Alt_L" in MODIFIER_ONLY_KEYS
        assert "Alt_R" in MODIFIER_ONLY_KEYS
        assert "Super_L" in MODIFIER_ONLY_KEYS
        assert "Super_R" in MODIFIER_ONLY_KEYS

    def test_regular_key_not_in_modifier_only(self):
        """
        GIVEN: Regular key names
        WHEN: Checked against MODIFIER_ONLY_KEYS
        THEN: Should not be present
        """
        # GIVEN
        regular_keys = ["a", "k", "F1", "Return", "Escape"]

        # WHEN / THEN
        for key in regular_keys:
            assert key not in MODIFIER_ONLY_KEYS
