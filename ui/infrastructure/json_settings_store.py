"""JSON-based settings storage implementation.

Replaces the GSettings/D-Bus extension-based settings store with a simple
JSON file at ~/.config/tfcbm/settings.json. Works on any DE.
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

from ui.domain.keyboard import KeyboardShortcut
from ui.interfaces.settings import ISettingsStore

logger = logging.getLogger("TFCBM.JsonSettingsStore")


class JsonSettingsStore(ISettingsStore):
    """Settings store using a JSON file backend. DE-agnostic."""

    DEFAULT_SHORTCUT = KeyboardShortcut(modifiers=["Ctrl"], key="Escape")

    def __init__(self):
        xdg_config_home = os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))
        self.config_dir = Path(xdg_config_home) / 'tfcbm'
        self.config_path = self.config_dir / 'settings.json'

    def _load_config(self) -> dict:
        """Load the full config dict from JSON file."""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error("Error loading settings: %s", e)
        return {}

    def _save_config(self, config: dict):
        """Save the full config dict to JSON file."""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2)
        except IOError as e:
            logger.error("Error saving settings: %s", e)

    def get_shortcut(self) -> Optional[KeyboardShortcut]:
        """Read the current keyboard shortcut from JSON settings."""
        config = self._load_config()
        shortcut_str = config.get('keyboard_shortcut')

        if not shortcut_str:
            logger.debug("No shortcut in settings, returning default")
            return self.DEFAULT_SHORTCUT

        try:
            return KeyboardShortcut.from_gtk_string(shortcut_str)
        except Exception as e:
            logger.error("Error parsing shortcut '%s': %s", shortcut_str, e)
            return self.DEFAULT_SHORTCUT

    def set_shortcut(self, shortcut: KeyboardShortcut) -> bool:
        """Write a keyboard shortcut to JSON settings."""
        try:
            config = self._load_config()
            config['keyboard_shortcut'] = shortcut.to_gtk_string()
            self._save_config(config)
            logger.info("Shortcut saved: %s", shortcut.to_display_string())
            return True
        except Exception as e:
            logger.error("Error saving shortcut: %s", e)
            return False

    def start_monitoring(self) -> bool:
        """No-op for JSON store. Monitoring is handled by ClipboardMonitor."""
        return True

    def stop_monitoring(self) -> bool:
        """No-op for JSON store."""
        return True

    def enable_keybinding(self) -> bool:
        """No-op for JSON store. Keybinding is handled by pynput/global shortcut service."""
        return True

    def disable_keybinding(self) -> bool:
        """No-op for JSON store."""
        return True
