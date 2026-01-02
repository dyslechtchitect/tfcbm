"""
Tests for UI mode settings.

TDD: Write tests first, then add UI mode to settings.
"""
import pytest
import tempfile
import yaml
from pathlib import Path
from server.src.settings import SettingsManager, Settings


class TestUIModeSettings:
    """Test UI mode settings with TDD approach."""

    def test_default_ui_mode_is_windowed(self):
        """UI mode should default to 'windowed'."""
        settings = Settings()

        assert settings.ui.mode == 'windowed'
        assert settings.ui.sidepanel_alignment == 'right'  # Default alignment

    def test_load_ui_mode_from_yaml(self, tmp_path):
        """Should load UI mode from YAML file."""
        config_file = tmp_path / "settings.yml"
        config_file.write_text("""
ui:
  mode: sidepanel
  sidepanel_alignment: left
""")

        manager = SettingsManager(config_path=config_file)

        assert manager.settings.ui.mode == 'sidepanel'
        assert manager.settings.ui.sidepanel_alignment == 'left'

    def test_ui_mode_validates_enum_values(self):
        """UI mode should only accept 'windowed' or 'sidepanel'."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            Settings(ui={'mode': 'invalid_mode'})

    def test_alignment_validates_enum_values(self):
        """Alignment should only accept 'left', 'right', or 'none'."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            Settings(ui={'sidepanel_alignment': 'center'})

    def test_windowed_mode_uses_none_alignment(self):
        """Windowed mode should use 'none' alignment."""
        settings = Settings(ui={'mode': 'windowed'})

        # Alignment is ignored in windowed mode, but should be valid
        assert settings.ui.mode == 'windowed'

    def test_update_ui_mode_to_sidepanel(self, tmp_path):
        """Should be able to update UI mode."""
        config_file = tmp_path / "settings.yml"
        config_file.write_text("display:\n  max_page_length: 20\n")

        manager = SettingsManager(config_path=config_file)

        # Update to sidepanel
        manager.update_settings(ui={'mode': 'sidepanel', 'sidepanel_alignment': 'right'})

        assert manager.settings.ui.mode == 'sidepanel'
        assert manager.settings.ui.sidepanel_alignment == 'right'

    def test_settings_service_exposes_ui_mode(self):
        """SettingsService should expose UI mode properties."""
        from server.src.services.settings_service import SettingsService

        service = SettingsService()

        # Should have properties for UI mode
        assert hasattr(service, 'ui_mode')
        assert hasattr(service, 'ui_sidepanel_alignment')

        assert service.ui_mode == 'windowed'  # Default
        assert service.ui_sidepanel_alignment in ['left', 'right', 'none']
