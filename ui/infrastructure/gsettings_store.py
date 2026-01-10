"""GSettings-based settings storage implementation."""

import os
import subprocess
from pathlib import Path
from typing import Optional

import gi
gi.require_version("Gio", "2.0")
gi.require_version("GLib", "2.0")
import logging
from gi.repository import Gio, GLib

logger = logging.getLogger("TFCBM.GSettingsStore")

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
        # schema_dir is no longer directly used for Flatpak's GSettings access,
        # but might be kept for native installations or context.

    def get_shortcut(self) -> Optional[KeyboardShortcut]:
        """
        Read the current keyboard shortcut from GSettings via the host extension's D-Bus.

        Returns:
            KeyboardShortcut if configured, None otherwise
        """
        try:
            # Assumes the host extension exposes a D-Bus service for its settings
            # The D-Bus service name and object path need to be confirmed from the extension
            proxy = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SESSION,
                Gio.DBusProxyFlags.NONE,
                None, # GDBusInterfaceInfo
                "org.gnome.Shell.Extensions.TfcbmClipboardMonitor", # Host extension's D-Bus service name
                "/org/gnome/Shell/Extensions/TfcbmClipboardMonitor", # Host extension's D-Bus object path
                "org.gnome.Shell.Extensions.TfcbmClipboardMonitor", # Interface name
                None # GCancellable
            )
            # Call a D-Bus method to get the setting
            # Assumes the host extension has a method like GetSetting(schema_id, key)
            result = proxy.call_sync(
                "GetSetting",
                GLib.Variant("(ss)", (self.schema_id, self.key)),
                Gio.DBusCallFlags.NONE,
                2000, # 2 second timeout to avoid blocking startup
                None # GCancellable
            )
            # result is a GLib.Variant, e.g., (s) for a string
            gsettings_value = result.unpack()[0] # Unpack the string value

            if gsettings_value:
                return KeyboardShortcut.from_gsettings_array(gsettings_value)
            return None
        except GLib.Error as e:
            logger.error(f"Error reading shortcut from host extension via D-Bus: {e.message}")
            return None
        except Exception as e:
            print(f"Unexpected error reading shortcut: {e}")
            return None

    def set_shortcut(self, shortcut: KeyboardShortcut) -> bool:
        """
        Write a keyboard shortcut to GSettings via the host extension's D-Bus.

        Args:
            shortcut: The shortcut to save

        Returns:
            True if successful, False otherwise
        """
        try:
            proxy = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SESSION,
                Gio.DBusProxyFlags.NONE,
                None, # GDBusInterfaceInfo
                "org.gnome.Shell.Extensions.TfcbmClipboardMonitor", # Host extension's D-Bus service name
                "/org/gnome/Shell/Extensions/TfcbmClipboardMonitor", # Host extension's D-Bus object path
                "org.gnome.Shell.Extensions.TfcbmClipboardMonitor", # Interface name
                None # GCancellable
            )
            # Call a D-Bus method to set the setting
            # Assumes the host extension has a method like SetSetting(schema_id, key, value)
            proxy.call_sync(
                "SetSetting",
                GLib.Variant("(sss)", (self.schema_id, self.key, shortcut.to_gsettings_string())),
                Gio.DBusCallFlags.NONE,
                5000, # 5 second timeout (writing might take longer)
                None # GCancellable
            )
            logger.debug(f"Shortcut set via D-Bus: {shortcut.to_gsettings_string()}")
            return True
        except GLib.Error as e:
            logger.error(f"Error writing shortcut to host extension via D-Bus: {e.message}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error writing shortcut: {e}")
            return False

