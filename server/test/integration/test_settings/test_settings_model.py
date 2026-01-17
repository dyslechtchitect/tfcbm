"""Tests for settings model validation."""

import pytest
from dataclasses import asdict

from settings import Settings, DisplaySettings, RetentionSettings, ClipboardSettings


class TestSettingsModelValidation:
    """Test settings model validation."""

    def test_valid_display_settings(self):
        """Test creating valid display settings."""
        settings = DisplaySettings(
            max_page_length=50,
            item_width=300,
            item_height=250
        )

        assert settings.max_page_length == 50
        assert settings.item_width == 300
        assert settings.item_height == 250

    def test_valid_retention_settings(self):
        """Test creating valid retention settings."""
        settings = RetentionSettings(
            enabled=True,
            max_items=500
        )

        assert settings.enabled is True
        assert settings.max_items == 500

    def test_invalid_retention_max_items_too_low(self):
        """Test that max_items below 10 raises error."""
        with pytest.raises(ValueError):
            RetentionSettings(max_items=5)

    def test_invalid_retention_max_items_too_high(self):
        """Test that max_items above 10000 raises error."""
        with pytest.raises(ValueError):
            RetentionSettings(max_items=20000)

    def test_settings_serialization_to_yaml(self):
        """Test settings serialization to dict (for YAML)."""
        settings = Settings(
            display=DisplaySettings(max_page_length=30),
            retention=RetentionSettings(max_items=300)
        )

        data = asdict(settings)

        assert data["display"]["max_page_length"] == 30
        assert data["retention"]["max_items"] == 300

    def test_settings_deserialization_from_yaml(self):
        """Test settings deserialization from dict (YAML data)."""
        data = {
            "display": {
                "max_page_length": 40,
                "item_width": 250,
                "item_height": 220
            },
            "retention": {
                "enabled": False,
                "max_items": 1000
            }
        }

        settings = Settings(
            display=DisplaySettings(**data.get('display', {})),
            retention=RetentionSettings(**data.get('retention', {})),
            clipboard=ClipboardSettings(**data.get('clipboard', {}))
        )

        assert settings.display.max_page_length == 40
        assert settings.display.item_width == 250
        assert settings.retention.enabled is False
        assert settings.retention.max_items == 1000

    def test_display_settings_defaults(self):
        """Test default values for display settings."""
        settings = DisplaySettings()

        assert settings.max_page_length == 20
        assert settings.item_width == 200
        assert settings.item_height == 200

    def test_retention_settings_defaults(self):
        """Test default values for retention settings."""
        settings = RetentionSettings()

        assert settings.enabled is True
        assert settings.max_items == 250

    def test_item_size_minimum_enforced(self):
        """Test that item width/height have minimum of 50."""
        # Values below 50 should raise validation error (not clamped)
        with pytest.raises(ValueError):
            DisplaySettings(item_width=30, item_height=40)

    def test_page_length_validation(self):
        """Test page length validation."""
        with pytest.raises(ValueError):
            DisplaySettings(max_page_length=0)

        with pytest.raises(ValueError):
            DisplaySettings(max_page_length=200)

    def test_item_size_maximum_enforced(self):
        """Test that item dimensions cannot exceed 1000."""
        with pytest.raises(ValueError):
            DisplaySettings(item_width=1500)

        with pytest.raises(ValueError):
            DisplaySettings(item_height=2000)

    def test_clipboard_settings_defaults(self):
        """Test default values for clipboard settings."""
        settings = ClipboardSettings()

        assert settings.refocus_on_copy is True

    def test_clipboard_settings_custom_values(self):
        """Test creating clipboard settings with custom values."""
        settings = ClipboardSettings(refocus_on_copy=False)

        assert settings.refocus_on_copy is False

    def test_settings_includes_clipboard_settings(self):
        """Test that main Settings includes clipboard settings."""
        settings = Settings()

        assert hasattr(settings, 'clipboard')
        assert isinstance(settings.clipboard, ClipboardSettings)
        assert settings.clipboard.refocus_on_copy is True

    def test_settings_with_clipboard_settings(self):
        """Test creating Settings with clipboard configuration."""
        data = {
            "display": {
                "max_page_length": 40,
                "item_width": 250,
                "item_height": 220
            },
            "retention": {
                "enabled": False,
                "max_items": 1000
            },
            "clipboard": {
                "refocus_on_copy": False
            }
        }

        settings = Settings(
            display=DisplaySettings(**data.get('display', {})),
            retention=RetentionSettings(**data.get('retention', {})),
            clipboard=ClipboardSettings(**data.get('clipboard', {}))
        )

        assert settings.clipboard.refocus_on_copy is False

    def test_clipboard_settings_serialization(self):
        """Test clipboard settings serialization to dict (for YAML)."""
        settings = Settings(
            clipboard=ClipboardSettings(refocus_on_copy=False)
        )

        data = asdict(settings)

        assert "clipboard" in data
        assert data["clipboard"]["refocus_on_copy"] is False
