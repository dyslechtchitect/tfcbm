#!/usr/bin/env python3
"""
TFCBM Settings Management
Loads and validates settings from settings.json using dataclasses
"""

import json
import os
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class DisplaySettings:
    """Display-related settings"""
    max_page_length: int = 20
    item_width: int = 200
    item_height: int = 200

    def __post_init__(self):
        """Validate settings"""
        if not 1 <= self.max_page_length <= 100:
            raise ValueError("max_page_length must be between 1 and 100")
        if not 50 <= self.item_width <= 1000:
            raise ValueError("item_width must be between 50 and 1000")
        if not 50 <= self.item_height <= 1000:
            raise ValueError("item_height must be between 50 and 1000")


@dataclass
class RetentionSettings:
    """Retention policy settings"""
    enabled: bool = True
    max_items: int = 250

    def __post_init__(self):
        """Validate settings"""
        if not 10 <= self.max_items <= 10000:
            raise ValueError("max_items must be between 10 and 10000")


@dataclass
class ClipboardSettings:
    """Clipboard behavior settings"""
    refocus_on_copy: bool = True


@dataclass
class ApplicationSettings:
    """Application behavior settings"""
    autostart_enabled: bool = False


@dataclass
class Settings:
    """Main settings model"""
    display: DisplaySettings = field(default_factory=DisplaySettings)
    retention: RetentionSettings = field(default_factory=RetentionSettings)
    clipboard: ClipboardSettings = field(default_factory=ClipboardSettings)
    application: ApplicationSettings = field(default_factory=ApplicationSettings)


class SettingsManager:
    """Manages loading and accessing settings"""

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize settings manager

        Args:
            config_path: Path to settings.json file. Defaults to ~/.config/tfcbm/settings.json
        """
        if config_path is None:
            # Use XDG_CONFIG_HOME for user settings (writable in Flatpak)
            xdg_config_home = os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')
            config_dir = Path(xdg_config_home) / 'tfcbm'
            config_path = config_dir / 'settings.json'

            # Ensure config directory exists
            config_dir.mkdir(parents=True, exist_ok=True)

        self.config_path = config_path
        self.settings = self._load_settings()

    def _load_settings(self) -> Settings:
        """Load and validate settings from JSON file"""
        try:
            if not self.config_path.exists():
                print(f"Settings file not found at {self.config_path}, using defaults")
                return Settings()

            with open(self.config_path, 'r') as f:
                config_data = json.load(f)

            if config_data is None:
                print("Settings file is empty, using defaults")
                return Settings()

            # Validate and create settings object
            settings = Settings(
                display=DisplaySettings(**config_data.get('display', {})),
                retention=RetentionSettings(**config_data.get('retention', {})),
                clipboard=ClipboardSettings(**config_data.get('clipboard', {})),
                application=ApplicationSettings(**config_data.get('application', {}))
            )
            print(f"Loaded settings from {self.config_path}")
            print(f"  - Max page length: {settings.display.max_page_length}")
            return settings

        except (json.JSONDecodeError, ValueError) as e:
            print(f"Error loading or validating settings: {e}")
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

    @property
    def refocus_on_copy(self) -> bool:
        """Get the refocus on copy setting"""
        return self.settings.clipboard.refocus_on_copy

    @property
    def autostart_enabled(self) -> bool:
        """Get the autostart enabled setting"""
        return self.settings.application.autostart_enabled

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
        """Save current settings to JSON file"""
        config_data = asdict(self.settings)
        with open(self.config_path, 'w') as f:
            json.dump(config_data, f, indent=2)


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
