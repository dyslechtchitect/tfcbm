"""GSettings-based settings storage implementation."""

import os
import subprocess
from pathlib import Path
from typing import Optional

from ui.domain.keyboard import KeyboardShortcut
from ui.interfaces.settings import ISettingsStore


class GSettingsStore(ISettingsStore):
    """Settings store using GNOME GSettings backend."""

    def __init__(self, schema_id: str, key: str, schema_dir: Optional[Path] = None):
        """
        Initialize GSettings store.

        Args:
            schema_id: GSettings schema ID (e.g., "org.gnome.shell.extensions.simple-clipboard")
            key: Key name within the schema (e.g., "toggle-tfcbm-ui")
            schema_dir: Optional directory containing compiled schemas
        """
        self.schema_id = schema_id
        self.key = key
        self.schema_dir = schema_dir

    def _get_env_with_schema_dir(self) -> dict:
        """
        Create environment dict with GSETTINGS_SCHEMA_DIR set.

        Returns:
            Environment dictionary
        """
        env = os.environ.copy()

        if self.schema_dir and Path(self.schema_dir).exists():
            schema_dir_str = str(self.schema_dir)
            if "GSETTINGS_SCHEMA_DIR" in env:
                env["GSETTINGS_SCHEMA_DIR"] = (
                    f"{schema_dir_str}:{env['GSETTINGS_SCHEMA_DIR']}"
                )
            else:
                env["GSETTINGS_SCHEMA_DIR"] = schema_dir_str

        return env

    def _get_gsettings_command(self, args: list[str]) -> list[str]:
        """
        Build gsettings command, using flatpak-spawn if running in Flatpak.

        Args:
            args: gsettings command arguments

        Returns:
            Command to execute
        """
        from ui.utils.extension_check import is_flatpak

        cmd = []
        env = os.environ.copy()

        if self.schema_dir and Path(self.schema_dir).exists():
            schema_dir_str = str(self.schema_dir)
            if "GSETTINGS_SCHEMA_DIR" in env:
                env["GSETTINGS_SCHEMA_DIR"] = (
                    f"{schema_dir_str}:{env['GSETTINGS_SCHEMA_DIR']}"
                )
            else:
                env["GSETTINGS_SCHEMA_DIR"] = schema_dir_str
        else:
            # If schema_dir doesn't exist, GSETTINGS_SCHEMA_DIR shouldn't be set
            # as it might point to a non-existent path and cause issues.
            # In this case, gsettings will rely on system-wide schemas.
            if "GSETTINGS_SCHEMA_DIR" in env:
                del env["GSETTINGS_SCHEMA_DIR"]

        if is_flatpak():
            # Run gsettings on host system to access the same dconf database as GNOME Shell
            # Use --directory to set a working directory that exists on the host
            cmd.extend(["flatpak-spawn", "--host", "--directory=/tmp"])
            # Pass GSETTINGS_SCHEMA_DIR explicitly via --env
            if "GSETTINGS_SCHEMA_DIR" in env:
                cmd.append(f"--env=GSETTINGS_SCHEMA_DIR={env['GSETTINGS_SCHEMA_DIR']}")
                # Remove from env dict so it's not passed twice implicitly by subprocess
                del env["GSETTINGS_SCHEMA_DIR"]
            cmd.extend(["gsettings"] + args)
        else:
            cmd.extend(["gsettings"] + args)

        return cmd, env

    def get_shortcut(self) -> Optional[KeyboardShortcut]:
        """
        Read the current keyboard shortcut from GSettings.

        Returns:
            KeyboardShortcut if configured, None otherwise
        """
        try:
            cmd, env_vars = self._get_gsettings_command(["get", self.schema_id, self.key])

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=env_vars,
                timeout=5,
            )

            if result.returncode == 0 and result.stdout.strip():
                return KeyboardShortcut.from_gsettings_array(result.stdout)
            return None
        except (
            subprocess.TimeoutExpired,
            subprocess.CalledProcessError,
            ValueError,
        ) as e:
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
            cmd, env_vars = self._get_gsettings_command(["set", self.schema_id, self.key, gsettings_format])

            print(f"[DEBUG] Running command: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=env_vars,
                timeout=5,
            )

            if result.returncode != 0:
                print(f"[ERROR] gsettings command failed with code {result.returncode}")
                print(f"[ERROR] stdout: {result.stdout}")
                print(f"[ERROR] stderr: {result.stderr}")

            return result.returncode == 0
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
            print(f"Error writing GSettings: {e}")
            return False
