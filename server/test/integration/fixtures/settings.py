"""Settings fixtures for tests."""

import pytest
import tempfile
import yaml
from pathlib import Path
from typing import Generator

from settings import Settings, SettingsManager


@pytest.fixture
def default_settings() -> Settings:
    """Create default settings object."""
    return Settings()


@pytest.fixture
def temp_settings_file() -> Generator[Path, None, None]:
    """Create a temporary settings file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
        config_data = {
            'display': {
                'max_page_length': 20,
                'item_width': 200,
                'item_height': 200
            },
            'retention': {
                'enabled': True,
                'max_items': 250
            }
        }
        yaml.dump(config_data, f)
        settings_path = Path(f.name)

    yield settings_path

    # Clean up
    settings_path.unlink(missing_ok=True)


@pytest.fixture
def settings_manager(temp_settings_file: Path) -> SettingsManager:
    """Create a settings manager with temporary settings file."""
    return SettingsManager(config_path=temp_settings_file)


@pytest.fixture
def custom_settings_data() -> dict:
    """Custom settings data for testing."""
    return {
        'display': {
            'max_page_length': 50,
            'item_width': 300,
            'item_height': 250
        },
        'retention': {
            'enabled': False,
            'max_items': 500
        }
    }
