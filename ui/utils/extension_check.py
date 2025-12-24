"""GNOME Extension check utility."""

import subprocess
import logging
from pathlib import Path

logger = logging.getLogger("TFCBM.UI")

EXTENSION_UUID = "tfcbm-clipboard-monitor@github.com"


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
        # Check if extension is installed
        list_result = subprocess.run(
            ['gnome-extensions', 'list'],
            capture_output=True,
            text=True,
            timeout=5
        )

        if list_result.returncode == 0:
            installed_extensions = list_result.stdout.strip().split('\n')
            status['installed'] = EXTENSION_UUID in installed_extensions

            if status['installed']:
                # Check if extension is enabled
                info_result = subprocess.run(
                    ['gnome-extensions', 'info', EXTENSION_UUID],
                    capture_output=True,
                    text=True,
                    timeout=5
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
        # Find the extension directory in the project
        project_root = Path(__file__).parent.parent.parent
        extension_dir = project_root / "gnome-extension"

        if not extension_dir.exists():
            return False, f"Extension directory not found at {extension_dir}"

        # Create a temporary zip or use the install script
        install_script = extension_dir / "install.sh"

        if install_script.exists():
            result = subprocess.run(
                ['bash', str(install_script)],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(extension_dir)
            )

            if result.returncode == 0:
                logger.info("Extension installed successfully")
                return True, "Extension installed successfully"
            else:
                logger.error(f"Failed to install extension: {result.stderr}")
                return False, f"Installation failed: {result.stderr}"
        else:
            return False, "Installation script not found"

    except Exception as e:
        logger.error(f"Error installing extension: {e}")
        return False, str(e)


def enable_extension() -> tuple[bool, str]:
    """Enable the TFCBM GNOME extension.

    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        result = subprocess.run(
            ['gnome-extensions', 'enable', EXTENSION_UUID],
            capture_output=True,
            text=True,
            timeout=10
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
    project_root = Path(__file__).parent.parent.parent
    extension_dir = project_root / "gnome-extension"
    return f"bash {extension_dir}/install.sh"


def get_extension_enable_command() -> str:
    """Get the command to enable the extension.

    Returns:
        str: Command to run to enable the extension
    """
    return f"gnome-extensions enable {EXTENSION_UUID}"
