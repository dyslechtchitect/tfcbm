#!/usr/bin/env python3
"""
TFCBM UI - GTK4 clipboard manager interface
Minimal entry point - classes are in separate modules.
"""

import ctypes
import sys
from pathlib import Path

# Set process name to "tfcbm-ui" so system monitors show it correctly
try:
    libc = ctypes.CDLL("libc.so.6", use_errno=True)
    libc.prctl(15, b"tfcbm-ui", 0, 0, 0)  # PR_SET_NAME = 15
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

import gi

gi.require_version("Gtk", "4.0")

import logging
import os

from gi.repository import GLib # GLib for get_user_data_dir

# Set GLib program name so KDE/GNOME system monitor can match to desktop file for icon
GLib.set_prgname("io.github.dyslechtchitect.tfcbm")

# Get Flatpak's user data directory for logs
log_dir = Path(GLib.get_user_data_dir()) / "tfcbm" # Create a subdirectory for logs
log_dir.mkdir(parents=True, exist_ok=True) # Ensure directory exists
log_file_path = log_dir / "tfcbm_ui_debug.log"

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file_path, mode='a', delay=False), # Append mode, no delay
        logging.StreamHandler(sys.stdout) # Keep console output as well
    ]
)
logger = logging.getLogger("TFCBM.UI")
logger.info(f"Logging to file: {log_file_path}")



def main():
    """Entry point"""
    from ui.application.clipboard_app import main as app_main

    logger.info("TFCBM UI starting...")

    # app_main() already runs the app and returns exit code
    return app_main()


if __name__ == "__main__":
    sys.exit(main() or 0)

