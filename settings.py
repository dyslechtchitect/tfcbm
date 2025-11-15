#!/usr/bin/env python3
"""
TFCBM Settings Management
Loads and validates settings from settings.yml using Pydantic
"""

import yaml
from pathlib import Path
from pydantic import BaseModel, Field, field_validator
from typing import Optional


class DisplaySettings(BaseModel):
    """Display-related settings"""
    max_page_length: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of items to load per page (1-100)"
    )

    @field_validator('max_page_length')
    @classmethod
    def validate_page_length(cls, v: int) -> int:
        """Ensure page length is reasonable"""
        if v < 1:
            raise ValueError("max_page_length must be at least 1")
        if v > 100:
            raise ValueError("max_page_length cannot exceed 100")
        return v


class Settings(BaseModel):
    """Main settings model"""
    display: DisplaySettings = Field(default_factory=DisplaySettings)


class SettingsManager:
    """Manages loading and accessing settings"""

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize settings manager

        Args:
            config_path: Path to settings.yml file. Defaults to ./settings.yml
        """
        if config_path is None:
            config_path = Path(__file__).parent / "settings.yml"

        self.config_path = config_path
        self.settings = self._load_settings()

    def _load_settings(self) -> Settings:
        """Load and validate settings from YAML file"""
        try:
            if not self.config_path.exists():
                print(f"Settings file not found at {self.config_path}, using defaults")
                return Settings()

            with open(self.config_path, 'r') as f:
                config_data = yaml.safe_load(f)

            if config_data is None:
                print("Settings file is empty, using defaults")
                return Settings()

            # Validate and create settings object
            settings = Settings(**config_data)
            print(f"Loaded settings from {self.config_path}")
            print(f"  - Max page length: {settings.display.max_page_length}")
            return settings

        except yaml.YAMLError as e:
            print(f"Error parsing settings YAML: {e}")
            print("Using default settings")
            return Settings()
        except Exception as e:
            print(f"Error loading settings: {e}")
            print("Using default settings")
            return Settings()

    def reload(self):
        """Reload settings from file"""
        self.settings = self._load_settings()

    @property
    def max_page_length(self) -> int:
        """Get the maximum page length setting"""
        return self.settings.display.max_page_length


# Global settings instance
_settings_manager: Optional[SettingsManager] = None


def get_settings() -> SettingsManager:
    """Get the global settings manager instance"""
    global _settings_manager
    if _settings_manager is None:
        _settings_manager = SettingsManager()
    return _settings_manager


if __name__ == "__main__":
    # Test the settings loader
    settings = get_settings()
    print(f"\nSettings loaded successfully!")
    print(f"Max page length: {settings.max_page_length}")
