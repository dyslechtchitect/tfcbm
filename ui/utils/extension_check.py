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
            'ready': bool,  # True if installed AND enabled AND D-Bus service is running
            'needs_enable': bool  # True if installed but not enabled
        }
    """
    status = {
        'installed': False,
        'enabled': False,
        'ready': False,
        'needs_enable': False
    }

    if is_flatpak():
        # In Flatpak, check for the host extension's D-Bus service
        try:
            # Attempt to create a D-Bus proxy for the host extension
            # Note: new_for_bus_sync doesn't fail if service doesn't exist,
            # we must check if the proxy has a name owner
            proxy = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SESSION,
                Gio.DBusProxyFlags.NONE,
                None, # GDBusInterfaceInfo
                "org.gnome.Shell.Extensions.TfcbmClipboardMonitor", # Host extension's D-Bus service name
                "/org/gnome/Shell/Extensions/TfcbmClipboardMonitor", # Host extension's D-Bus object path
                "org.gnome.Shell.Extensions.TfcbmClipboardMonitor", # Interface name
                None # GCancellable
            )

            # Check if the service actually exists by verifying it has a name owner
            name_owner = proxy.get_name_owner()
            if name_owner:
                # Service is running, so the extension is installed and enabled
                status['installed'] = True
                status['enabled'] = True
                status['ready'] = True
                logger.info(f"Host extension D-Bus service 'org.gnome.Shell.Extensions.TfcbmClipboardMonitor' found (owner: {name_owner}).")
            else:
                logger.info("Host extension D-Bus service not found (no name owner).")
                # Check if extension files exist on disk (installed but not running)
                extension_path = Path.home() / ".local" / "share" / "gnome-shell" / "extensions" / EXTENSION_UUID
                if extension_path.exists() and (extension_path / "extension.js").exists():
                    logger.info(f"Extension files found at {extension_path} but D-Bus service not running")
                    status['installed'] = True
                    status['needs_enable'] = True
        except GLib.Error as e:
            logger.info(f"Host extension D-Bus service not found or error: {e.message}")
            # Check if extension files exist on disk
            extension_path = Path.home() / ".local" / "share" / "gnome-shell" / "extensions" / EXTENSION_UUID
            if extension_path.exists() and (extension_path / "extension.js").exists():
                logger.info(f"Extension files found at {extension_path} but D-Bus service error")
                status['installed'] = True
                status['needs_enable'] = True
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

            # First check if extension files exist on disk
            extension_path = Path.home() / ".local" / "share" / "gnome-shell" / "extensions" / EXTENSION_UUID
            files_installed = extension_path.exists() and (extension_path / "extension.js").exists()
            logger.info(f"Extension files on disk: {files_installed} at {extension_path}")

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
                gnome_knows_about_it = EXTENSION_UUID in installed_extensions
                # Consider installed if either GNOME knows about it OR files exist on disk
                status['installed'] = gnome_knows_about_it or files_installed

                if gnome_knows_about_it:
                    # GNOME Shell knows about the extension, check its state
                    info_result = subprocess.run(
                        ['gnome-extensions', 'info', EXTENSION_UUID],
                        capture_output=True,
                        text=True,
                        timeout=10,
                        env=env
                    )

                    if info_result.returncode == 0:
                        output = info_result.stdout
                        # Check if enabled (can be ENABLED, ACTIVE, or even INITIALIZED if recently enabled)
                        is_enabled_flag = 'Enabled: Yes' in output or 'Enabled: yes' in output
                        is_active_state = 'State: ENABLED' in output or 'State: ACTIVE' in output
                        is_initialized = 'State: INITIALIZED' in output

                        status['enabled'] = is_enabled_flag or is_active_state
                        # Consider ready if it's active OR if it's enabled and initialized (will be active after restart)
                        status['ready'] = is_active_state or (is_enabled_flag and is_initialized)
                        # Needs enable if installed but not enabled
                        status['needs_enable'] = not (is_enabled_flag or is_active_state)
                        logger.info(f"Extension state output: {output[:100]}")
                        logger.info(f"Extension status flags: enabled_flag={is_enabled_flag}, active={is_active_state}, initialized={is_initialized}")
                elif files_installed:
                    # Extension files exist but GNOME Shell doesn't know about them yet
                    # This means GNOME Shell needs to be restarted
                    logger.info("Extension files installed but GNOME Shell hasn't loaded them yet")
                    status['enabled'] = False
                    status['ready'] = False  # Needs GNOME Shell restart
                    status['needs_enable'] = True

                logger.info(f"Extension status: installed={status['installed']}, enabled={status['enabled']}, ready={status['ready']}")
            else:
                logger.warning(f"Failed to list extensions (returncode={list_result.returncode})")
                logger.warning(f"stdout: {list_result.stdout}")
                logger.warning(f"stderr: {list_result.stderr}")
                # Even if gnome-extensions command failed, check if files exist
                status['installed'] = files_installed
                if files_installed:
                    logger.info("Extension files exist on disk even though gnome-extensions command failed")
                    status['enabled'] = False
                    status['ready'] = False

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
        # In Flatpak, use GNOME Shell D-Bus API to enable extension
        try:
            proxy = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SESSION,
                Gio.DBusProxyFlags.NONE,
                None,
                "org.gnome.Shell.Extensions",
                "/org/gnome/Shell/Extensions",
                "org.gnome.Shell.Extensions",
                None
            )

            # Call EnableExtension method
            proxy.call_sync(
                "EnableExtension",
                GLib.Variant("(s)", (EXTENSION_UUID,)),
                Gio.DBusCallFlags.NONE,
                5000,  # 5 second timeout
                None
            )

            logger.info("Extension enabled successfully via D-Bus")
            return True, "Extension enabled successfully"

        except GLib.Error as e:
            logger.error(f"Failed to enable extension via D-Bus: {e.message}")
            return False, f"Failed to enable extension: {e.message}"
        except Exception as e:
            logger.error(f"Unexpected error enabling extension: {e}")
            return False, str(e)

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
        return f"Please run 'tfcbm-install-extension' from your terminal to install the GNOME Shell Extension, or install it from extensions.gnome.org. Ensure you have 'gnome-extensions' tool installed on your host system."
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


def uninstall_extension() -> tuple[bool, str]:
    """Uninstall the TFCBM GNOME extension.

    This should be called before the user uninstalls the Flatpak app
    to ensure the extension is properly cleaned up.

    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        # First, disable the extension
        logger.info("Disabling extension before removal...")
        try:
            if is_flatpak():
                # Use D-Bus to disable
                proxy = Gio.DBusProxy.new_for_bus_sync(
                    Gio.BusType.SESSION,
                    Gio.DBusProxyFlags.NONE,
                    None,
                    "org.gnome.Shell.Extensions",
                    "/org/gnome/Shell/Extensions",
                    "org.gnome.Shell.Extensions",
                    None
                )
                proxy.call_sync(
                    "DisableExtension",
                    GLib.Variant("(s)", (EXTENSION_UUID,)),
                    Gio.DBusCallFlags.NONE,
                    5000,
                    None
                )
                logger.info("✓ Extension disabled via D-Bus")
            else:
                # Use gnome-extensions command
                env = os.environ.copy()
                common_paths = '/usr/bin:/usr/local/bin:/bin:/snap/bin'
                if 'PATH' not in env:
                    env['PATH'] = common_paths
                elif common_paths not in env['PATH']:
                    env['PATH'] = f"{common_paths}:{env['PATH']}"

                subprocess.run(
                    ['gnome-extensions', 'disable', EXTENSION_UUID],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    env=env
                )
                logger.info("✓ Extension disabled via command")
        except Exception as disable_error:
            logger.warning(f"Could not disable extension (may already be disabled): {disable_error}")
            # Continue with removal anyway

        # Remove extension files
        extension_path = Path.home() / ".local" / "share" / "gnome-shell" / "extensions" / EXTENSION_UUID

        if extension_path.exists():
            import shutil
            logger.info(f"Removing extension files from {extension_path}")
            shutil.rmtree(extension_path)
            logger.info("✓ Extension files removed successfully")
            return True, "Extension uninstalled successfully"
        else:
            logger.info("Extension files not found (may already be removed)")
            return True, "Extension was not installed"

    except Exception as e:
        logger.error(f"Error uninstalling extension: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False, f"Failed to uninstall extension: {e}"


def install_extension() -> tuple[bool, str]:
    """Install the TFCBM GNOME extension.

    Returns:
        tuple: (success: bool, message: str)
    """
    if is_flatpak():
        # In Flatpak, copy extension files directly to user's extension directory
        # InstallRemoteExtension only works for extensions published on extensions.gnome.org
        # Our extension is bundled with the app, so we need to copy files directly
        try:
            # Find the bundled extension directory in the Flatpak
            # Extensions are bundled at /app/share/gnome-shell/extensions/
            extension_source = Path(f"/app/share/gnome-shell/extensions/{EXTENSION_UUID}")

            if not extension_source.exists():
                logger.error(f"Extension files not found at {extension_source}")
                return False, f"Extension files not bundled in application. Please contact support."

            # Use direct file copy method since this is a local extension
            return _install_extension_direct()

        except Exception as e:
            logger.error(f"Unexpected error installing extension: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False, str(e)

    else:
        # Native installation using install script
        project_root = Path(__file__).parent.parent.parent
        extension_dir = project_root / "gnome-extension"
        install_script = extension_dir / "install.sh"

        if not install_script.exists():
            return False, f"Install script not found at {install_script}"

        try:
            env = os.environ.copy()
            common_paths = '/usr/bin:/usr/local/bin:/bin:/snap/bin'
            if 'PATH' not in env:
                env['PATH'] = common_paths
            elif common_paths not in env['PATH']:
                env['PATH'] = f"{common_paths}:{env['PATH']}"

            result = subprocess.run(
                ['bash', str(install_script)],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(extension_dir),
                env=env
            )

            if result.returncode == 0:
                logger.info("Extension installed successfully")
                return True, "Extension installed successfully. Please enable it by running: gnome-extensions enable tfcbm-clipboard-monitor@github.com"
            else:
                logger.error(f"Failed to install extension: {result.stderr}")
                return False, f"Failed to install: {result.stderr}"

        except Exception as e:
            logger.error(f"Error installing extension: {e}")
            return False, str(e)


def _install_extension_direct() -> tuple[bool, str]:
    """Install extension by copying files directly to user's extension directory.

    This is a fallback method when D-Bus InstallRemoteExtension fails.

    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        import shutil

        # Extension source in Flatpak
        extension_source = Path(f"/app/share/gnome-shell/extensions/{EXTENSION_UUID}")

        # Destination in user's home directory
        extensions_dir = Path.home() / ".local" / "share" / "gnome-shell" / "extensions"
        extension_dest = extensions_dir / EXTENSION_UUID

        # Create extensions directory if it doesn't exist
        extensions_dir.mkdir(parents=True, exist_ok=True)

        # Remove existing installation if present
        if extension_dest.exists():
            shutil.rmtree(extension_dest)

        # Copy extension files
        shutil.copytree(extension_source, extension_dest)

        logger.info(f"Extension files copied to {extension_dest}")

        # Compile GSettings schemas (CRITICAL: required for extension settings to work)
        schemas_dir = extension_dest / "schemas"
        if schemas_dir.exists():
            try:
                logger.info(f"Compiling GSettings schemas in {schemas_dir}")
                result = subprocess.run(
                    ['glib-compile-schemas', str(schemas_dir)],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    logger.info("✓ GSettings schemas compiled successfully")
                else:
                    logger.error(f"Failed to compile schemas: {result.stderr}")
                    return False, f"Extension installed but schema compilation failed: {result.stderr}"
            except Exception as schema_error:
                logger.error(f"Error compiling schemas: {schema_error}")
                return False, f"Extension installed but schema compilation failed: {schema_error}"
        else:
            logger.warning(f"No schemas directory found at {schemas_dir}")

        return True, "Extension installed successfully. Please enable it by running: gnome-extensions enable tfcbm-clipboard-monitor@github.com"

    except Exception as e:
        logger.error(f"Failed to install extension directly: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False, f"Failed to copy extension files: {e}"
