"""GNOME Extension check utility."""

import subprocess
import logging

logger = logging.getLogger("TFCBM.UI")

EXTENSION_UUID = "tfcbm-clipboard-monitor@github.com"


def is_extension_installed() -> bool:
    """Check if the TFCBM GNOME extension is installed.

    Returns:
        bool: True if extension is installed, False otherwise
    """
    try:
        result = subprocess.run(
            ['gnome-extensions', 'list'],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            installed_extensions = result.stdout.strip().split('\n')
            is_installed = EXTENSION_UUID in installed_extensions
            logger.info(f"Extension check: {EXTENSION_UUID} {'found' if is_installed else 'NOT found'}")
            return is_installed
        else:
            logger.error(f"Failed to list extensions: {result.stderr}")
            return False

    except FileNotFoundError:
        logger.error("gnome-extensions command not found")
        return False
    except Exception as e:
        logger.error(f"Error checking extension: {e}")
        return False


def get_extension_install_command() -> str:
    """Get the command to install the extension.

    Returns:
        str: Command to run to install the extension
    """
    # For now, this would be a manual install from the repo
    # In the future, this could point to GNOME Extensions website
    return "cd /path/to/TFCBM && ./install.sh"
