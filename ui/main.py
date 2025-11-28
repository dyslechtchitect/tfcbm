#!/usr/bin/env python3
"""
TFCBM UI - GTK4 clipboard manager interface
Minimal entry point - classes are in separate modules.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

import logging
import signal

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("TFCBM.UI")


def main():
    """Entry point"""
    from ui.application.clipboard_app import main as app_main

    logger.info("TFCBM UI starting...")

    def signal_handler(sig, frame):
        print("Shutting down UI...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    return app_main()


if __name__ == "__main__":
    main()
