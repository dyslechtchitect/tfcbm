"""GSettings-based settings storage implementation."""
import os
import subprocess
from pathlib import Path
from typing import Optional

from src.config import ApplicationConfig
from src.domain.keyboard import KeyboardShortcut
from src.interfaces.settings import ISettingsStore


class GSettingsStore(ISettingsStore):
    """Settings store using GNOME GSettings backend."""

    def __init__(self, config: ApplicationConfig):
        """
        Initialize GSettings store.

        Args:
            config: Application configuration
        """
        self.config = config

    def _get_env_with_schema_dir(self) -> dict:
        """
        Create environment dict with GSETTINGS_SCHEMA_DIR set.

        Returns:
            Environment dictionary
        """
        env = os.environ.copy()
        schema_dir = str(self.config.schema_dir)

        if Path(schema_dir).exists():
            if "GSETTINGS_SCHEMA_DIR" in env:
                env["GSETTINGS_SCHEMA_DIR"] = f"{schema_dir}:{env['GSETTINGS_SCHEMA_DIR']}"
            else:
                env["GSETTINGS_SCHEMA_DIR"] = schema_dir

        return env

    def get_shortcut(self) -> Optional[KeyboardShortcut]:
        """
        Read the current keyboard shortcut from GSettings.

        Returns:
            KeyboardShortcut if configured, None otherwise
        """
        try:
            result = subprocess.run(
                [
                    "gsettings", "get",
                    self.config.gsettings_schema,
                    self.config.gsettings_key
                ],
                capture_output=True,
                text=True,
                env=self._get_env_with_schema_dir(),
                timeout=5
            )

            if result.returncode == 0 and result.stdout.strip():
                return KeyboardShortcut.from_gsettings_array(result.stdout)
            return None
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, ValueError) as e:
            print(f"Error reading GSettings: {e}")
            return None

    def set_shortcut(self, shortcut: KeyboardShortcut) -> bool:
        """
        Write a keyboard shortcut to GSettings.

        Args:
            shortcut: The shortcut to save

        Returns:
            True if successful, False otherwise
        """
        try:
            gsettings_format = f"['{shortcut.to_gsettings_string()}']"
            result = subprocess.run(
                [
                    "gsettings", "set",
                    self.config.gsettings_schema,
                    self.config.gsettings_key,
                    gsettings_format
                ],
                capture_output=True,
                text=True,
                env=self._get_env_with_schema_dir(),
                timeout=5
            )

            return result.returncode == 0
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
            print(f"Error writing GSettings: {e}")
            return False
