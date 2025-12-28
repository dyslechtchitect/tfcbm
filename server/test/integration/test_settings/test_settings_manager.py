"""Tests for SettingsManager."""

import pytest
import tempfile
import yaml
from pathlib import Path

from settings import SettingsManager, Settings
from fixtures.settings import temp_settings_file, settings_manager, custom_settings_data


class TestSettingsManager:
    """Test SettingsManager functionality."""

    def test_load_from_default_path(self, temp_settings_file: Path):
        """Test loading settings from file."""
        manager = SettingsManager(config_path=temp_settings_file)

        assert manager.max_page_length == 20
        assert manager.retention_max_items == 250

    def test_load_from_custom_path(self, custom_settings_data: dict):
        """Test loading from custom path."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            yaml.dump(custom_settings_data, f)
            custom_path = Path(f.name)

        try:
            manager = SettingsManager(config_path=custom_path)

            assert manager.max_page_length == 50
            assert manager.item_width == 300
            assert manager.retention_enabled is False
            assert manager.retention_max_items == 500
        finally:
            custom_path.unlink(missing_ok=True)

    def test_load_missing_file_uses_defaults(self, tmp_path: Path):
        """Test that missing file results in default settings."""
        nonexistent_path = tmp_path / "nonexistent.yml"

        manager = SettingsManager(config_path=nonexistent_path)

        # Should use defaults
        assert manager.max_page_length == 20
        assert manager.retention_max_items == 250

    def test_save_settings_to_file(self, settings_manager: SettingsManager, temp_settings_file: Path):
        """Test saving settings to file."""
        settings_manager.update_settings(**{"retention.max_items": 500})

        # Read file and verify
        with open(temp_settings_file, 'r') as f:
            data = yaml.safe_load(f)

        assert data["retention"]["max_items"] == 500

    def test_update_nested_settings(self, settings_manager: SettingsManager):
        """Test updating nested settings."""
        settings_manager.update_settings(**{"display.item_width": 350})

        assert settings_manager.item_width == 350

    def test_property_accessors_work_correctly(self, settings_manager: SettingsManager):
        """Test property accessor methods."""
        assert settings_manager.max_page_length == 20
        assert settings_manager.item_width == 200
        assert settings_manager.item_height == 200
        assert settings_manager.retention_enabled is True
        assert settings_manager.retention_max_items == 250

    def test_reload_settings(self, settings_manager: SettingsManager, temp_settings_file: Path):
        """Test reloading settings from file."""
        # Modify file directly
        new_data = {
            'display': {'max_page_length': 75, 'item_width': 200, 'item_height': 200},
            'retention': {'enabled': True, 'max_items': 1000}
        }
        with open(temp_settings_file, 'w') as f:
            yaml.dump(new_data, f)

        # Reload
        settings_manager.reload()

        assert settings_manager.max_page_length == 75
        assert settings_manager.retention_max_items == 1000

    def test_handle_corrupted_yaml(self, tmp_path: Path):
        """Test handling of corrupted YAML file."""
        corrupted_path = tmp_path / "corrupted.yml"
        with open(corrupted_path, 'w') as f:
            f.write("invalid: yaml: content: [[[")

        manager = SettingsManager(config_path=corrupted_path)

        # Should fall back to defaults
        assert manager.max_page_length == 20

    def test_handle_empty_yaml_file(self, tmp_path: Path):
        """Test handling of empty YAML file."""
        empty_path = tmp_path / "empty.yml"
        empty_path.touch()

        manager = SettingsManager(config_path=empty_path)

        # Should use defaults
        assert manager.max_page_length == 20
        assert manager.retention_max_items == 250
