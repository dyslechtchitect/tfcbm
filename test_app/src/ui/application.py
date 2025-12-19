"""GTK Application class."""
from typing import Optional

from gi.repository import Adw, Gio

from src.application.activation_tracker import ActivationTracker
from src.application.shortcut_service import ShortcutService
from src.config import ApplicationConfig
from src.interfaces.keyboard_input import IKeyboardEventParser
from src.ui.window import ShortcutRecorderWindow


class ShortcutRecorderApp(Adw.Application):
    """Main GTK application with GAction support."""

    def __init__(
        self,
        config: ApplicationConfig,
        shortcut_service: ShortcutService,
        activation_tracker: ActivationTracker,
        keyboard_parser: IKeyboardEventParser
    ):
        """
        Initialize the application.

        Args:
            config: Application configuration
            shortcut_service: Service for managing shortcuts
            activation_tracker: Tracker for activation events
            keyboard_parser: Parser for keyboard events
        """
        super().__init__(
            application_id=config.app_id,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS
        )
        self.config = config
        self.shortcut_service = shortcut_service
        self.activation_tracker = activation_tracker
        self.keyboard_parser = keyboard_parser
        self.window: Optional[ShortcutRecorderWindow] = None

    def do_startup(self) -> None:
        """Set up the application on startup."""
        Adw.Application.do_startup(self)

        # Create the show-window GAction
        show_action = Gio.SimpleAction.new("show-window", None)
        show_action.connect("activate", self._on_show_window_action)
        self.add_action(show_action)

        print(f"[POC] Application started - GAction 'show-window' registered")
        print(f"[POC] DBus name: {self.config.dbus_name}")
        print(f"[POC] DBus path: {self.config.dbus_path}")

    def do_activate(self) -> None:
        """Create and present the main window."""
        if not self.window:
            self.window = ShortcutRecorderWindow(
                application=self,
                config=self.config,
                shortcut_service=self.shortcut_service,
                activation_tracker=self.activation_tracker,
                keyboard_parser=self.keyboard_parser
            )
            print("[POC] Window created")

        self.window.present()
        print("[POC] Window presented")

    def _on_show_window_action(
        self,
        action: Gio.SimpleAction,
        parameter: Optional[object]
    ) -> None:
        """
        Handle the show-window GAction.

        Called by the GNOME Shell extension via DBus.

        Args:
            action: The action that was triggered
            parameter: Action parameters (unused)
        """
        print("[POC] show-window action triggered!")

        if not self.window:
            self.window = ShortcutRecorderWindow(
                application=self,
                config=self.config,
                shortcut_service=self.shortcut_service,
                activation_tracker=self.activation_tracker,
                keyboard_parser=self.keyboard_parser
            )

        # Toggle window visibility
        if self.window.is_visible():
            print("[POC] Hiding window")
            self.window.set_visible(False)
        else:
            print("[POC] Showing window via GAction")
            self.window.set_visible(True)
            self.window.present()
            # Notify that it was activated via shortcut
            self.window.on_shortcut_activated()
