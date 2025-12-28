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
    item_width: int = Field(
        default=200,
        ge=50,
        le=1000,
        description="Width of clipboard item cards in pixels (50-1000)"
    )
    item_height: int = Field(
        default=200,
        ge=50,
        le=1000,
        description="Height of clipboard item cards in pixels (50-1000)"
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

    @field_validator('item_width', 'item_height')
    @classmethod
    def validate_item_size(cls, v: int) -> int:
        """Ensure item size is at least 50x50"""
        if v < 50:
            return 50
        if v > 1000:
            raise ValueError("item dimensions cannot exceed 1000")
        return v


class RetentionSettings(BaseModel):
    """Retention policy settings"""
    enabled: bool = Field(
        default=True,
        description="Enable automatic cleanup of old items"
    )
    max_items: int = Field(
        default=250,
        ge=10,
        le=10000,
        description="Maximum number of items to retain (10-10000)"
    )

    @field_validator('max_items')
    @classmethod
    def validate_max_items(cls, v: int) -> int:
        """Ensure max_items is reasonable"""
        if v < 10:
            raise ValueError("max_items must be at least 10")
        if v > 10000:
            raise ValueError("max_items cannot exceed 10000")
        return v


class Settings(BaseModel):
    """Main settings model"""
    display: DisplaySettings = Field(default_factory=DisplaySettings)
    retention: RetentionSettings = Field(default_factory=RetentionSettings)


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

    @property
    def item_width(self) -> int:
        """Get the item width setting"""
        return self.settings.display.item_width

    @property
    def item_height(self) -> int:
        """Get the item height setting"""
        return self.settings.display.item_height

    @property
    def retention_enabled(self) -> bool:
        """Get the retention enabled setting"""
        return self.settings.retention.enabled

    @property
    def retention_max_items(self) -> int:
        """Get the retention max items setting"""
        return self.settings.retention.max_items

    def update_settings(self, **kwargs):
        """Update settings and save to file"""
        # Update the settings object
        for key, value in kwargs.items():
            if '.' in key:
                # Handle nested settings like 'display.item_width'
                parts = key.split('.')
                obj = self.settings
                for part in parts[:-1]:
                    obj = getattr(obj, part)
                setattr(obj, parts[-1], value)
            else:
                setattr(self.settings, key, value)

        # Save to file
        self._save_settings()

    def _save_settings(self):
        """Save current settings to YAML file"""
        import yaml
        config_data = self.settings.model_dump()
        with open(self.config_path, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False)


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
