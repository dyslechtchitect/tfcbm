"""GNOME Extension check utility."""

import subprocess
import logging
import os
from pathlib import Path

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


def _get_command_prefix() -> list[str]:
    """Get the command prefix needed to run host commands.

    Returns:
        list: Command prefix (empty for normal, flatpak-spawn for Flatpak)
    """
    if is_flatpak():
        # Use flatpak-spawn with --host and set working directory to home
        return ['flatpak-spawn', '--host', '--directory=/home']
    return []


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

    try:
        # Ensure we have the right environment
        env = os.environ.copy()
        if 'PATH' not in env or '/usr/bin' not in env['PATH']:
            env['PATH'] = f"/usr/bin:/bin:{env.get('PATH', '')}"

        # Check if extension is installed
        cmd_prefix = _get_command_prefix()
        list_result = subprocess.run(
            cmd_prefix + ['gnome-extensions', 'list'],
            capture_output=True,
            text=True,
            timeout=5,
            env=env
        )

        if list_result.returncode == 0:
            installed_extensions = list_result.stdout.strip().split('\n')
            status['installed'] = EXTENSION_UUID in installed_extensions

            if status['installed']:
                # Check if extension is enabled
                info_result = subprocess.run(
                    cmd_prefix + ['gnome-extensions', 'info', EXTENSION_UUID],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    env=env
                )

                if info_result.returncode == 0:
                    # Parse output to check state
                    output = info_result.stdout
                    status['enabled'] = 'State: ENABLED' in output or 'State: ACTIVE' in output
                    status['ready'] = status['enabled']

            logger.info(f"Extension status: installed={status['installed']}, enabled={status['enabled']}")
        else:
            logger.error(f"Failed to list extensions: {list_result.stderr}")

    except FileNotFoundError:
        logger.error("gnome-extensions command not found")
    except Exception as e:
        logger.error(f"Error checking extension: {e}")

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


def install_extension() -> tuple[bool, str]:
    """Install the TFCBM GNOME extension from the bundled copy.

    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        # In Flatpak, use the bundled zip file directly
        if is_flatpak():
            extension_zip = Path("/app/share/tfcbm/tfcbm-clipboard-monitor@github.com.zip")
            logger.info(f"Running in Flatpak, using extension zip: {extension_zip}")

            if not extension_zip.exists():
                error_msg = f"Extension zip not found at {extension_zip}"
                logger.error(error_msg)
                parent_dir = extension_zip.parent
                if parent_dir.exists():
                    logger.error(f"Contents of {parent_dir}: {list(parent_dir.iterdir())}")
                return False, error_msg

            # Copy the zip to a location that the host can access
            # The host can't access /app/ since that's inside the Flatpak container
            # Use XDG_CACHE_HOME which is shared between Flatpak and host
            import shutil

            # Use XDG_CACHE_HOME or fallback to ~/.cache
            cache_dir = Path(os.environ.get('XDG_CACHE_HOME', Path.home() / '.cache'))
            cache_dir.mkdir(parents=True, exist_ok=True)
            temp_zip = cache_dir / "tfcbm-clipboard-monitor@github.com.zip"
            logger.info(f"Copying extension zip to shared location: {temp_zip}")
            shutil.copy2(extension_zip, temp_zip)

            # Use gnome-extensions install command directly with the zip
            env = os.environ.copy()
            if 'PATH' not in env or '/usr/bin' not in env['PATH']:
                env['PATH'] = f"/usr/bin:/bin:{env.get('PATH', '')}"

            cmd_prefix = _get_command_prefix()

            # Install the extension from the temporary zip location
            logger.info(f"Installing extension from temporary zip: {temp_zip}")
            install_result = subprocess.run(
                cmd_prefix + ['gnome-extensions', 'install', '--force', str(temp_zip)],
                capture_output=True,
                text=True,
                timeout=30,
                env=env
            )

            if install_result.returncode != 0:
                error_msg = f"Failed to install extension: {install_result.stderr}"
                logger.error(error_msg)
                return False, error_msg

            logger.info("Extension installed successfully from zip")

            # Try to enable the extension
            enable_result = subprocess.run(
                cmd_prefix + ['gnome-extensions', 'enable', EXTENSION_UUID],
                capture_output=True,
                text=True,
                timeout=10,
                env=env
            )

            if enable_result.returncode == 0:
                logger.info("Extension enabled successfully")

                # Verify the extension state
                info_result = subprocess.run(
                    cmd_prefix + ['gnome-extensions', 'info', EXTENSION_UUID],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    env=env
                )

                if info_result.returncode == 0:
                    output = info_result.stdout
                    if 'State: ACTIVE' in output:
                        return True, "Extension installed and enabled successfully!"
                    else:
                        return True, "Extension installed and enabled! Please log out and log back in to activate it."
                else:
                    return True, "Extension installed and enabled! Please log out and log back in to activate it."
            else:
                logger.warning(f"Extension installed but failed to enable: {enable_result.stderr}")
                return True, "Extension installed! Please log out and log back in to activate it."

        # Non-Flatpak: use the directory method
        project_root = Path(__file__).parent.parent.parent
        extension_dir = project_root / "gnome-extension"
        logger.info(f"Regular install, using extension directory: {extension_dir}")

        if not extension_dir.exists():
            error_msg = f"Extension directory not found at {extension_dir}"
            logger.error(error_msg)
            return False, error_msg

        # Install manually to avoid interactive prompts in install.sh
        # Get UUID from metadata.json
        metadata_file = extension_dir / "metadata.json"
        if not metadata_file.exists():
            error_msg = f"metadata.json not found in {extension_dir}"
            logger.error(error_msg)
            logger.error(f"Extension dir contents: {list(extension_dir.iterdir()) if extension_dir.exists() else 'dir does not exist'}")
            return False, error_msg

        import json
        with open(metadata_file) as f:
            metadata = json.load(f)
            uuid = metadata.get("uuid")
            if not uuid:
                return False, "UUID not found in metadata.json"

        logger.info(f"Installing extension with UUID: {uuid}")

        # Define installation directory
        install_dir = Path.home() / ".local/share/gnome-shell/extensions" / uuid
        logger.info(f"Installing to: {install_dir}")

        # Remove old installation if exists
        if install_dir.exists():
            import shutil
            logger.info(f"Removing old installation at {install_dir}")
            shutil.rmtree(install_dir)

        # Create installation directory
        install_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created installation directory: {install_dir}")

        # Copy extension files
        import shutil
        files_to_copy = ["extension.js", "metadata.json", "tfcbm.svg"]
        for file in files_to_copy:
            src = extension_dir / file
            if src.exists():
                dest = install_dir / file
                shutil.copy2(src, dest)
                logger.info(f"Copied {file} to {dest}")
            else:
                logger.warning(f"File not found: {src}")

        # Copy directories
        dirs_to_copy = ["src", "schemas"]
        for dir_name in dirs_to_copy:
            src_dir = extension_dir / dir_name
            if src_dir.exists():
                dest_dir = install_dir / dir_name
                shutil.copytree(src_dir, dest_dir, dirs_exist_ok=True)
                logger.info(f"Copied directory {dir_name} to {dest_dir}")
            else:
                logger.warning(f"Directory not found: {src_dir}")

        # Ensure we have the right environment
        env = os.environ.copy()
        if 'PATH' not in env or '/usr/bin' not in env['PATH']:
            env['PATH'] = f"/usr/bin:/bin:{env.get('PATH', '')}"

        cmd_prefix = _get_command_prefix()

        # Compile GSettings schema if schemas exist
        schemas_dir = install_dir / "schemas"
        if schemas_dir.exists():
            logger.info(f"Compiling GSettings schemas in {schemas_dir}")
            result = subprocess.run(
                cmd_prefix + ["glib-compile-schemas", str(schemas_dir)],
                capture_output=True,
                text=True,
                timeout=10,
                env=env
            )
            if result.returncode != 0:
                logger.warning(f"Failed to compile schemas: {result.stderr}")
            else:
                logger.info("GSettings schemas compiled successfully")

        # Set permissions
        logger.info(f"Setting permissions on {install_dir}")
        subprocess.run(cmd_prefix + ["chmod", "-R", "755", str(install_dir)], timeout=5, env=env)

        # Verify installation
        if not install_dir.exists() or not (install_dir / "metadata.json").exists():
            error_msg = "Installation verification failed - files not copied correctly"
            logger.error(error_msg)
            return False, error_msg

        logger.info("Extension files verified successfully")

        # Try to enable the extension immediately
        try:
            enable_result = subprocess.run(
                cmd_prefix + ['gnome-extensions', 'enable', EXTENSION_UUID],
                capture_output=True,
                text=True,
                timeout=10,
                env=env
            )
            if enable_result.returncode == 0:
                logger.info("Extension enabled successfully")

                # Verify the extension is actually active
                info_result = subprocess.run(
                    cmd_prefix + ['gnome-extensions', 'info', EXTENSION_UUID],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    env=env
                )

                if info_result.returncode == 0:
                    output = info_result.stdout
                    if 'State: ACTIVE' in output:
                        logger.info("Extension is now active and ready to use!")
                        return True, "Extension installed and enabled successfully!"
                    else:
                        logger.warning(f"Extension enabled but not active yet. State: {output}")
                        return True, "Extension installed and enabled! Please log out and log back in to activate it."
                else:
                    logger.warning("Could not verify extension state")
                    return True, "Extension installed and enabled! Please log out and log back in to activate it."
            else:
                error_msg = f"Failed to enable extension: {enable_result.stderr}"
                logger.error(error_msg)
                return False, error_msg

        except Exception as e:
            error_msg = f"Error enabling extension: {e}"
            logger.error(error_msg)
            return False, error_msg

    except FileNotFoundError as e:
        logger.error(f"FileNotFoundError installing extension: {e}")
        logger.error(f"Exception details: filename={e.filename}, strerror={e.strerror}")
        return False, f"File not found: {e.filename} - {e.strerror}"
    except Exception as e:
        logger.error(f"Error installing extension: {e}")
        logger.error(f"Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False, str(e)


def enable_extension() -> tuple[bool, str]:
    """Enable the TFCBM GNOME extension.

    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        # Ensure we have the right environment
        env = os.environ.copy()
        if 'PATH' not in env or '/usr/bin' not in env['PATH']:
            env['PATH'] = f"/usr/bin:/bin:{env.get('PATH', '')}"

        cmd_prefix = _get_command_prefix()
        result = subprocess.run(
            cmd_prefix + ['gnome-extensions', 'enable', EXTENSION_UUID],
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
    """Get the command to install the extension.

    Returns:
        str: Command to run to install the extension
    """
    # Check if running in Flatpak
    if is_flatpak():
        # Use the flatpak-install-extension command that's bundled with the flatpak
        # This is more reliable than trying to guess the flatpak installation path
        return "flatpak run --command=tfcbm-install-extension org.tfcbm.ClipboardManager"
    else:
        # Regular install - extension is in project directory
        project_root = Path(__file__).parent.parent.parent
        extension_dir = project_root / "gnome-extension"
        # Return command that changes directory first, then runs install script
        return f"cd {extension_dir} && ./install.sh"


def get_extension_enable_command() -> str:
    """Get the command to enable the extension.

    Returns:
        str: Command to run to enable the extension
    """
    return f"gnome-extensions enable {EXTENSION_UUID}"
