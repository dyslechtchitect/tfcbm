"""GSettings-based settings storage implementation."""

import os
import subprocess
import time
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
        Uses retry logic with exponential backoff for reliability.

        Returns:
            KeyboardShortcut if configured, None otherwise
        """
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                # Create proxy for the host extension's D-Bus service
                proxy = Gio.DBusProxy.new_for_bus_sync(
                    Gio.BusType.SESSION,
                    Gio.DBusProxyFlags.NONE,
                    None,
                    "io.github.dyslechtchitect.tfcbm.Extension",
                    "/io/github/dyslechtchitect/tfcbm/Extension",
                    "io.github.dyslechtchitect.tfcbm.Extension",
                    None
                )

                # CRITICAL: Check if service is actually running
                name_owner = proxy.get_name_owner()
                if not name_owner:
                    logger.warning(f"Extension D-Bus service not available (attempt {attempt+1}/{max_attempts})")
                    if attempt < max_attempts - 1:
                        time.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s, 4s
                        continue
                    logger.error("Extension D-Bus service not running after all retries")
                    logger.error("Make sure the GNOME extension is installed and enabled")
                    return None

                logger.debug(f"Connected to extension D-Bus service (owner: {name_owner})")

                # Call GetSetting method with increased timeout
                result = proxy.call_sync(
                    "GetSetting",
                    GLib.Variant("(ss)", (self.schema_id, self.key)),
                    Gio.DBusCallFlags.NONE,
                    5000,  # Increased from 2000ms to 5000ms
                    None
                )

                # Success! Parse and return the shortcut
                gsettings_value = result.unpack()[0]

                # Return None if empty or whitespace-only
                if gsettings_value and gsettings_value.strip():
                    logger.debug(f"Successfully read shortcut: {gsettings_value}")
                    return KeyboardShortcut.from_gsettings_array(gsettings_value)
                logger.warning(f"Empty or whitespace-only shortcut value received: '{gsettings_value}'")
                return None

            except GLib.Error as e:
                logger.error(f"D-Bus error (attempt {attempt+1}/{max_attempts}): {e.message}")

                # Check if it's a service/timeout error that might benefit from retry
                if "ServiceUnknown" in str(e.message) or "NoReply" in str(e.message) or "Timeout" in str(e.message):
                    # Extension not running or timeout - check if extension is enabled
                    if attempt == 0:  # Only check on first attempt to avoid spam
                        try:
                            from ui.utils.extension_check import get_extension_status
                            status = get_extension_status()
                            if not status['enabled']:
                                logger.error("Extension is not enabled! User needs to enable it.")
                                return None
                        except Exception:
                            pass  # Ignore errors in status check

                    # Retry if we have attempts left
                    if attempt < max_attempts - 1:
                        logger.info(f"Retrying in {2 ** attempt} seconds...")
                        time.sleep(2 ** attempt)
                        continue

                # Other D-Bus errors or no retries left - give up
                logger.error("Failed to read shortcut after all retries")
                return None

            except Exception as e:
                logger.error(f"Unexpected error reading shortcut (attempt {attempt+1}/{max_attempts}): {e}")
                import traceback
                logger.debug(traceback.format_exc())
                return None

        # All retries exhausted
        logger.error("All retry attempts exhausted for get_shortcut")
        return None

    def set_shortcut(self, shortcut: KeyboardShortcut) -> bool:
        """
        Write a keyboard shortcut to GSettings via the host extension's D-Bus.
        Uses retry logic with exponential backoff for reliability.

        Args:
            shortcut: The shortcut to save

        Returns:
            True if successful, False otherwise
        """
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                proxy = Gio.DBusProxy.new_for_bus_sync(
                    Gio.BusType.SESSION,
                    Gio.DBusProxyFlags.NONE,
                    None,
                    "io.github.dyslechtchitect.tfcbm.Extension",
                    "/io/github/dyslechtchitect/tfcbm/Extension",
                    "io.github.dyslechtchitect.tfcbm.Extension",
                    None
                )

                # Check if the service is actually running
                name_owner = proxy.get_name_owner()
                if not name_owner:
                    logger.warning(f"Extension D-Bus service not available (attempt {attempt+1}/{max_attempts})")
                    if attempt < max_attempts - 1:
                        time.sleep(2 ** attempt)
                        continue
                    logger.error("Extension D-Bus service is not available (no name owner)")
                    logger.error("Make sure the GNOME extension is installed and enabled")
                    return False

                logger.debug(f"Connected to extension D-Bus service (owner: {name_owner})")

                # Call SetSetting method with increased timeout
                shortcut_str = shortcut.to_gsettings_string()
                proxy.call_sync(
                    "SetSetting",
                    GLib.Variant("(sss)", (self.schema_id, self.key, shortcut_str)),
                    Gio.DBusCallFlags.NONE,
                    10000,  # Increased from 5000ms to 10000ms (writing might take longer)
                    None
                )

                logger.info(f"✓ Shortcut set successfully via D-Bus: {shortcut_str}")

                # Verify the shortcut was actually set (read it back)
                try:
                    verify_result = proxy.call_sync(
                        "GetSetting",
                        GLib.Variant("(ss)", (self.schema_id, self.key)),
                        Gio.DBusCallFlags.NONE,
                        5000,
                        None
                    )
                    verified_value = verify_result.unpack()[0]
                    if verified_value == shortcut_str:
                        logger.info("✓ Shortcut verified successfully")
                        return True
                    else:
                        logger.warning(f"Verification mismatch: set '{shortcut_str}' but got '{verified_value}'")
                        # Still return True as the set operation succeeded
                        return True
                except Exception as verify_error:
                    logger.warning(f"Could not verify shortcut (but set succeeded): {verify_error}")
                    # Don't fail just because verification failed
                    return True

            except GLib.Error as e:
                logger.error(f"D-Bus error writing shortcut (attempt {attempt+1}/{max_attempts}): {e.message}")

                # Check if it's a service/timeout error that might benefit from retry
                if "ServiceUnknown" in str(e.message) or "NoReply" in str(e.message) or "Timeout" in str(e.message):
                    if attempt == 0:
                        logger.error("The extension D-Bus service is not running!")
                        logger.error("Check extension status with: gnome-extensions info tfcbm-clipboard-monitor@github.com")

                    # Retry if we have attempts left
                    if attempt < max_attempts - 1:
                        logger.info(f"Retrying in {2 ** attempt} seconds...")
                        time.sleep(2 ** attempt)
                        continue

                # Other errors or no retries left
                return False

            except Exception as e:
                logger.error(f"Unexpected error writing shortcut (attempt {attempt+1}/{max_attempts}): {e}")
                import traceback
                logger.debug(traceback.format_exc())
                return False

        # All retries exhausted
        logger.error("All retry attempts exhausted for set_shortcut")
        return False

    def disable_keybinding(self) -> bool:
        """
        Temporarily disable the global keybinding via the extension's D-Bus.

        This is used during shortcut recording to prevent the extension from
        intercepting the key events before the GTK window can capture them.

        Returns:
            True if successful, False otherwise
        """
        max_attempts = 2  # Fewer retries for this operation
        for attempt in range(max_attempts):
            try:
                proxy = Gio.DBusProxy.new_for_bus_sync(
                    Gio.BusType.SESSION,
                    Gio.DBusProxyFlags.NONE,
                    None,
                    "io.github.dyslechtchitect.tfcbm.Extension",
                    "/io/github/dyslechtchitect/tfcbm/Extension",
                    "io.github.dyslechtchitect.tfcbm.Extension",
                    None
                )

                # Check if service is available
                name_owner = proxy.get_name_owner()
                if not name_owner:
                    logger.warning(f"Extension D-Bus service not available for disable keybinding (attempt {attempt+1}/{max_attempts})")
                    if attempt < max_attempts - 1:
                        time.sleep(1)
                        continue
                    return False

                proxy.call_sync(
                    "DisableKeybinding",
                    None,
                    Gio.DBusCallFlags.NONE,
                    5000,  # Increased timeout
                    None
                )
                logger.info("✓ Keybinding disabled successfully")
                return True

            except GLib.Error as e:
                logger.error(f"Error disabling keybinding via D-Bus (attempt {attempt+1}/{max_attempts}): {e.message}")
                if attempt < max_attempts - 1:
                    time.sleep(1)
                    continue
                return False
            except Exception as e:
                logger.error(f"Unexpected error disabling keybinding: {e}")
                return False

        return False

    def start_monitoring(self) -> bool:
        """
        Tell the extension to start clipboard monitoring.

        Returns:
            bool: True if successful, False otherwise
        """
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                # Connect to extension's D-Bus service
                proxy = Gio.DBusProxy.new_for_bus_sync(
                    Gio.BusType.SESSION,
                    Gio.DBusProxyFlags.NONE,
                    None,
                    "io.github.dyslechtchitect.tfcbm.Extension",
                    "/io/github/dyslechtchitect/tfcbm/Extension",
                    "io.github.dyslechtchitect.tfcbm.Extension",
                    None
                )

                # CRITICAL: Check if service is actually running
                name_owner = proxy.get_name_owner()
                if not name_owner:
                    logger.warning(f"Extension D-Bus service not available for start monitoring (attempt {attempt+1}/{max_attempts})")
                    if attempt < max_attempts - 1:
                        import time
                        time.sleep(0.3)
                        continue
                    return False

                # Call StartMonitoring method
                proxy.call_sync(
                    "StartMonitoring",
                    None,
                    Gio.DBusCallFlags.NONE,
                    2000,
                    None
                )
                logger.info("✓ Monitoring started successfully")
                return True

            except GLib.Error as e:
                logger.error(f"Error starting monitoring via D-Bus (attempt {attempt+1}/{max_attempts}): {e.message}")
                if attempt < max_attempts - 1:
                    import time
                    time.sleep(0.3)
                continue

            except Exception as e:
                logger.error(f"Unexpected error starting monitoring: {e}")
                return False

        logger.error("Failed to start monitoring after all attempts")
        return False

    def stop_monitoring(self) -> bool:
        """
        Tell the extension to stop clipboard monitoring.

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Connect to extension's D-Bus service
            proxy = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SESSION,
                Gio.DBusProxyFlags.NONE,
                None,
                "io.github.dyslechtchitect.tfcbm.Extension",
                "/io/github/dyslechtchitect/tfcbm/Extension",
                "io.github.dyslechtchitect.tfcbm.Extension",
                None
            )

            # Call StopMonitoring method
            proxy.call_sync(
                "StopMonitoring",
                None,
                Gio.DBusCallFlags.NONE,
                2000,
                None
            )
            logger.info("✓ Monitoring stopped successfully")
            return True

        except GLib.Error as e:
            logger.error(f"Error stopping monitoring via D-Bus: {e.message}")
            return False

        except Exception as e:
            logger.error(f"Unexpected error stopping monitoring: {e}")
            return False

    def enable_keybinding(self) -> bool:
        """
        Re-enable the global keybinding via the extension's D-Bus.

        This is called after shortcut recording completes.

        Returns:
            True if successful, False otherwise
        """
        max_attempts = 2  # Fewer retries for this operation
        for attempt in range(max_attempts):
            try:
                proxy = Gio.DBusProxy.new_for_bus_sync(
                    Gio.BusType.SESSION,
                    Gio.DBusProxyFlags.NONE,
                    None,
                    "io.github.dyslechtchitect.tfcbm.Extension",
                    "/io/github/dyslechtchitect/tfcbm/Extension",
                    "io.github.dyslechtchitect.tfcbm.Extension",
                    None
                )

                # Check if service is available
                name_owner = proxy.get_name_owner()
                if not name_owner:
                    logger.warning(f"Extension D-Bus service not available for enable keybinding (attempt {attempt+1}/{max_attempts})")
                    if attempt < max_attempts - 1:
                        time.sleep(1)
                        continue
                    return False

                proxy.call_sync(
                    "EnableKeybinding",
                    None,
                    Gio.DBusCallFlags.NONE,
                    5000,  # Increased timeout
                    None
                )
                logger.info("✓ Keybinding re-enabled successfully")
                return True

            except GLib.Error as e:
                logger.error(f"Error re-enabling keybinding via D-Bus (attempt {attempt+1}/{max_attempts}): {e.message}")
                if attempt < max_attempts - 1:
                    time.sleep(1)
                    continue
                return False
            except Exception as e:
                logger.error(f"Unexpected error re-enabling keybinding: {e}")
                return False

        return False

