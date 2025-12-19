#!/usr/bin/env python3
"""
Shortcut Recorder POC - Entry point.

Demonstrates focus-stealing using GApplication Actions.
Records keyboard shortcuts and pops up when they're pressed.
"""
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")

from src.application.activation_tracker import ActivationTracker
from src.application.shortcut_service import ShortcutService
from src.config import DEFAULT_CONFIG
from src.infrastructure.gsettings_store import GSettingsStore
from src.infrastructure.gtk_keyboard_parser import GtkKeyboardEventParser
from src.ui.application import ShortcutRecorderApp


def create_app() -> ShortcutRecorderApp:
    """
    Create and configure the application with all dependencies.

    Returns:
        Configured ShortcutRecorderApp instance
    """
    # Configuration
    config = DEFAULT_CONFIG

    # Infrastructure implementations
    settings_store = GSettingsStore(config)
    keyboard_parser = GtkKeyboardEventParser()

    # Application services
    shortcut_service = ShortcutService(settings_store)
    activation_tracker = ActivationTracker()

    # Create application
    app = ShortcutRecorderApp(
        config=config,
        shortcut_service=shortcut_service,
        activation_tracker=activation_tracker,
        keyboard_parser=keyboard_parser
    )

    return app


def main() -> int:
    """
    Entry point for the application.

    Returns:
        Exit code
    """
    app = create_app()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
