"""Configuration constants and settings."""
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ApplicationConfig:
    """Application configuration constants."""

    app_id: str = "org.example.ShortcutRecorder"
    extension_uuid: str = "shortcut-recorder-poc@example.org"
    gsettings_schema: str = "org.gnome.shell.extensions.shortcut-recorder-poc"
    gsettings_key: str = "toggle-shortcut-recorder"
    default_shortcut: str = "<Ctrl><Shift>K"
    window_title: str = "Shortcut Recorder POC"
    window_width: int = 500
    window_height: int = 400

    @property
    def dbus_name(self) -> str:
        """Get DBus name from app ID."""
        return self.app_id

    @property
    def dbus_path(self) -> str:
        """Get DBus path from app ID."""
        return f"/{self.app_id.replace('.', '/')}"

    @property
    def extension_dir(self) -> Path:
        """Get extension installation directory."""
        return Path.home() / ".local/share/gnome-shell/extensions" / self.extension_uuid

    @property
    def schema_dir(self) -> Path:
        """Get GSettings schema directory."""
        return self.extension_dir / "schemas"


# Default configuration instance
DEFAULT_CONFIG = ApplicationConfig()
