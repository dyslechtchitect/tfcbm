"""GNOME Extension check utility."""

import subprocess
import logging
import os
from pathlib import Path

import gi
gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib # GLib is already imported by Gio, but good to be explicit

logger = logging.getLogger("TFCBM.UI")

EXTENSION_UUID = "tfcbm-clipboard-monitor@github.com"


def is_flatpak() -> bool:
    """Check if running inside a Flatpak sandbox.

    Returns:
        bool: True if running in Flatpak, False otherwise
    """
    # Check multiple indicators for Flatpak environment
    return (
        'FLATPAK_ID' in os.environ or
        os.path.exists('/.flatpak-info') or
        os.path.exists('/app')  # /app is the standard Flatpak mount point
    )


def get_extension_status() -> dict:
    """Check the status of the TFCBM GNOME extension.

    Returns:
        dict: {
            'installed': bool,
            'enabled': bool,
            'ready': bool  # True if installed AND enabled
        }
    """
    status = {
        'installed': False,
        'enabled': False,
        'ready': False
    }

    if is_flatpak():
        # In Flatpak, check for the host extension's D-Bus service
        try:
            # Attempt to create a D-Bus proxy for the host extension
            # If the service is not available, this will raise a Gio.DBusError
            proxy = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SESSION,
                Gio.DBusProxyFlags.NONE,
                None, # GDBusInterfaceInfo
                "org.gnome.Shell.Extensions.TfcbmClipboardMonitor", # Host extension's D-Bus service name
                "/org/gnome/Shell/Extensions/TfcbmClipboardMonitor", # Host extension's D-Bus object path
                "org.gnome.Shell.Extensions.TfcbmClipboardMonitor", # Interface name
                None # GCancellable
            )
            # If we reach here, the service is running, so the extension is installed and enabled.
            status['installed'] = True
            status['enabled'] = True
            status['ready'] = True
            logger.info("Host extension D-Bus service 'org.gnome.Shell.Extensions.TfcbmClipboardMonitor' found.")
        except GLib.Error as e:
            logger.info(f"Host extension D-Bus service not found or error: {e.message}")
        except Exception as e:
            logger.error(f"Unexpected error checking extension D-Bus service: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
        return status
    else:
        # Running natively, use subprocess to check with gnome-extensions command
        try:
            env = os.environ.copy()
            common_paths = '/usr/bin:/usr/local/bin:/bin:/snap/bin'
            if 'PATH' not in env:
                env['PATH'] = common_paths
            elif common_paths not in env['PATH']:
                env['PATH'] = f"{common_paths}:{env['PATH']}"

            logger.info(f"Checking extensions with command: {' '.join(['gnome-extensions', 'list'])}")

            list_result = subprocess.run(
                ['gnome-extensions', 'list'],
                capture_output=True,
                text=True,
                timeout=10,
                env=env
            )

            if list_result.returncode == 0:
                installed_extensions = list_result.stdout.strip().split('\n')
                logger.info(f"Found {len(installed_extensions)} extensions: {installed_extensions}")
                status['installed'] = EXTENSION_UUID in installed_extensions

                if status['installed']:
                    info_result = subprocess.run(
                        ['gnome-extensions', 'info', EXTENSION_UUID],
                        capture_output=True,
                        text=True,
                        timeout=10,
                        env=env
                    )

                    if info_result.returncode == 0:
                        output = info_result.stdout
                        status['enabled'] = 'State: ENABLED' in output or 'State: ACTIVE' in output
                        status['ready'] = status['enabled']
                        logger.info(f"Extension state output: {output[:100]}")

                logger.info(f"Extension status: installed={status['installed']}, enabled={status['enabled']}")
            else:
                logger.warning(f"Failed to list extensions (returncode={list_result.returncode})")
                logger.warning(f"stdout: {list_result.stdout}")
                logger.warning(f"stderr: {list_result.stderr}")
                status['installed'] = False

        except subprocess.TimeoutExpired:
            logger.error("Timeout checking extensions - assuming not installed")
            status['installed'] = False
        except FileNotFoundError as e:
            logger.error(f"gnome-extensions command not found: {e}")
            status['installed'] = False
        except Exception as e:
            logger.error(f"Error checking extension: {e}")
            logger.error(f"Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            status['installed'] = False

        return status

def is_extension_installed() -> bool:
    """Check if the TFCBM GNOME extension is installed.

    Returns:
        bool: True if extension is installed, False otherwise
    """
    status = get_extension_status()
    return status['installed']


def is_extension_ready() -> bool:
    """Check if the TFCBM GNOME extension is installed AND enabled.

    Returns:
        bool: True if extension is ready to use, False otherwise
    """
    status = get_extension_status()
    return status['ready']


def enable_extension() -> tuple[bool, str]:
    """Enable the TFCBM GNOME extension.

    Returns:
        tuple: (success: bool, message: str)
    """
    if is_flatpak():
        # In Flatpak, we can't enable the host extension from inside the sandbox
        return False, "Cannot enable extension from Flatpak. Please enable it manually on the host system using GNOME Extensions app or 'gnome-extensions enable tfcbm-clipboard-monitor@github.com'"

    try:
        env = os.environ.copy()
        common_paths = '/usr/bin:/usr/local/bin:/bin:/snap/bin'
        if 'PATH' not in env:
            env['PATH'] = common_paths
        elif common_paths not in env['PATH']:
            env['PATH'] = f"{common_paths}:{env['PATH']}"

        result = subprocess.run(
            ['gnome-extensions', 'enable', EXTENSION_UUID],
            capture_output=True,
            text=True,
            timeout=10,
            env=env
        )

        if result.returncode == 0:
            logger.info("Extension enabled successfully")
            return True, "Extension enabled successfully"
        else:
            logger.error(f"Failed to enable extension: {result.stderr}")
            return False, f"Failed to enable: {result.stderr}"

    except Exception as e:
        logger.error(f"Error enabling extension: {e}")
        return False, str(e)









def get_extension_install_command() -> str:
    """Get user instructions or command to install the extension.

    Returns:
        str: User-friendly instruction or command string.
    """
    if is_flatpak():
        return f"Please install the TFCBM GNOME Shell Extension from extensions.gnome.org or by running 'gnome-extensions install --force tfcbm-clipboard-monitor@github.com.zip' after downloading the zip manually. Also ensure you have 'gnome-extensions' tool installed on your host system."
    else:
        project_root = Path(__file__).parent.parent.parent
        extension_dir = project_root / "gnome-extension"
        return f"To install the TFCBM GNOME Shell Extension, navigate to the project's 'gnome-extension' directory and run './install.sh' from your terminal:\ncd {extension_dir} && ./install.sh"


def get_extension_enable_command() -> str:
    """Get user instructions or command to enable the extension.

    Returns:
        str: User-friendly instruction or command string.
    """
    if is_flatpak():
        return f"Please ensure the TFCBM GNOME Shell Extension is enabled. You can do this via GNOME Extensions app or by running 'gnome-extensions enable {EXTENSION_UUID}' on your host system."
    else:
        return f"To enable the TFCBM GNOME Shell Extension, run 'gnome-extensions enable {EXTENSION_UUID}' from your terminal."
