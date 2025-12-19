"""Main application window."""
from typing import Optional

from gi.repository import Adw, Gdk, GLib, Gtk

from src.application.activation_tracker import ActivationObserver, ActivationTracker
from src.application.shortcut_service import ShortcutObserver, ShortcutService
from src.config import ApplicationConfig
from src.domain.keyboard import KeyboardShortcut
from src.interfaces.keyboard_input import IKeyboardEventParser


class ShortcutRecorderWindow(Adw.ApplicationWindow):
    """Main window for recording and displaying keyboard shortcuts."""

    def __init__(
        self,
        config: ApplicationConfig,
        shortcut_service: ShortcutService,
        activation_tracker: ActivationTracker,
        keyboard_parser: IKeyboardEventParser,
        **kwargs
    ):
        """
        Initialize the window.

        Args:
            config: Application configuration
            shortcut_service: Service for managing shortcuts
            activation_tracker: Tracker for activation events
            keyboard_parser: Parser for keyboard events
            **kwargs: Additional GTK window arguments
        """
        super().__init__(**kwargs)
        self.config = config
        self.shortcut_service = shortcut_service
        self.activation_tracker = activation_tracker
        self.keyboard_parser = keyboard_parser

        # Setup window
        self.set_title(config.window_title)
        self.set_default_size(config.window_width, config.window_height)

        # Build UI
        self._build_ui()

        # Setup event handlers
        self._setup_event_handlers()

        # Register as observer
        self.shortcut_service.add_observer(self)
        self.activation_tracker.add_observer(self)

        # Initial display update
        self._update_current_shortcut_display()

    def _build_ui(self) -> None:
        """Build the user interface."""
        # Main container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        main_box.set_margin_top(20)
        main_box.set_margin_bottom(20)
        main_box.set_margin_start(20)
        main_box.set_margin_end(20)

        # Header
        header = Gtk.Label()
        header.set_markup("<big><b>Keyboard Shortcut Recorder</b></big>")
        main_box.append(header)

        # Instructions
        instructions = Gtk.Label(
            label=f"Press {self.config.default_shortcut} anywhere to toggle this window!\n\n"
                  "This demonstrates focus-stealing using GApplication Actions."
        )
        instructions.set_wrap(True)
        main_box.append(instructions)

        # Shortcut recorder frame
        shortcut_frame = self._build_shortcut_recorder_frame()
        main_box.append(shortcut_frame)

        # Status label
        self.status_label = Gtk.Label()
        self.status_label.set_markup("<i>Waiting for keyboard shortcut...</i>")
        main_box.append(self.status_label)

        # Activation counter
        self.counter_label = Gtk.Label()
        self._update_counter_display()
        main_box.append(self.counter_label)

        # Close button
        close_btn = Gtk.Button(label="Close Window")
        close_btn.connect("clicked", lambda _: self.close())
        close_btn.set_halign(Gtk.Align.CENTER)
        main_box.append(close_btn)

        self.set_content(main_box)

    def _build_shortcut_recorder_frame(self) -> Gtk.Frame:
        """Build the shortcut recorder UI section."""
        frame = Gtk.Frame()
        frame.set_label("Record New Shortcut")

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(10)
        box.set_margin_bottom(10)
        box.set_margin_start(10)
        box.set_margin_end(10)

        # Instructions
        instructions = Gtk.Label(
            label="Click 'Start Recording' and press any key combination"
        )
        box.append(instructions)

        # Display current shortcut
        self.shortcut_display = Gtk.Label()
        box.append(self.shortcut_display)

        # Recording button
        self.record_btn = Gtk.Button(label="Start Recording")
        self.record_btn.connect("clicked", self._on_record_button_clicked)
        self.record_btn.set_halign(Gtk.Align.CENTER)
        box.append(self.record_btn)

        # Recording status
        self.recording_status = Gtk.Label()
        box.append(self.recording_status)

        frame.set_child(box)
        return frame

    def _setup_event_handlers(self) -> None:
        """Setup keyboard event controller."""
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_controller)

    def _on_record_button_clicked(self, button: Gtk.Button) -> None:
        """Handle record button click."""
        is_recording = self.shortcut_service.toggle_recording()

        if is_recording:
            self.record_btn.set_label("Stop Recording")
            self.recording_status.set_markup("<i>Press any key combination...</i>")
        else:
            self.record_btn.set_label("Start Recording")
            self.recording_status.set_text("")

    def _on_key_pressed(
        self,
        controller: Gtk.EventControllerKey,
        keyval: int,
        keycode: int,
        state: int
    ) -> bool:
        """
        Handle key press events.

        Args:
            controller: Event controller
            keyval: GTK keyval
            keycode: Hardware keycode
            state: Modifier state

        Returns:
            True if event was handled
        """
        if not self.shortcut_service.is_recording:
            return False

        # Parse the key event
        event = self.keyboard_parser.parse_key_event(keyval, keycode, state)

        # Process it through the service
        shortcut = self.shortcut_service.process_key_event(event)

        if shortcut:
            # Display the recorded shortcut
            self._display_recorded_shortcut(shortcut)
            # Apply it to the extension
            self.shortcut_service.apply_shortcut(shortcut)
            return True

        return False

    def _display_recorded_shortcut(self, shortcut: KeyboardShortcut) -> None:
        """Display a newly recorded shortcut."""
        display_text = self._escape_markup(shortcut.to_gtk_string())
        self.shortcut_display.set_markup(f"<b>Recorded: {display_text}</b>")
        self.recording_status.set_markup(
            f"<span color='green'>✓ Recorded: {display_text}</span>\n"
            "<i>Applying to extension...</i>"
        )
        self.record_btn.set_label("Start Recording")

    def _update_current_shortcut_display(self) -> None:
        """Update the display with the current shortcut from settings."""
        current = self.shortcut_service.get_current_shortcut()

        if current:
            display_text = self._escape_markup(current.to_gtk_string())
            self.shortcut_display.set_markup(f"<b>Current: {display_text}</b>")
        else:
            default = self._escape_markup(self.config.default_shortcut)
            self.shortcut_display.set_markup(f"<b>Current: {default} (default)</b>")

    def _update_counter_display(self) -> None:
        """Update the activation counter display."""
        count = self.activation_tracker.count
        self.counter_label.set_markup(
            f"<b>Times activated via shortcut: {count}</b>"
        )

    def _reset_status_message(self) -> bool:
        """Reset the status message after a delay."""
        self.status_label.set_markup("<i>Waiting for keyboard shortcut...</i>")
        return False  # Don't repeat

    @staticmethod
    def _escape_markup(text: str) -> str:
        """Escape text for GTK markup."""
        return text.replace("<", "&lt;").replace(">", "&gt;")

    # Observer implementations

    def on_shortcut_recorded(self, shortcut: KeyboardShortcut) -> None:
        """Called when a shortcut is recorded (ShortcutObserver)."""
        # Already handled in _display_recorded_shortcut
        pass

    def on_shortcut_applied(self, shortcut: KeyboardShortcut, success: bool) -> None:
        """Called when a shortcut application completes (ShortcutObserver)."""
        display_text = self._escape_markup(shortcut.to_gtk_string())

        if success:
            self.recording_status.set_markup(
                f"<span color='green'>✓ Applied: {display_text}</span>\n"
                "<i>The new shortcut is now active!</i>"
            )
            self._update_current_shortcut_display()
        else:
            self.recording_status.set_markup(
                f"<span color='orange'>⚠ Recorded: {display_text}</span>\n"
                "<i>Could not apply to extension</i>"
            )

    def on_activation_count_changed(self, count: int) -> None:
        """Called when activation count changes (ActivationObserver)."""
        self._update_counter_display()
        self.status_label.set_markup(
            "<span color='green'><b>✓ Activated via keyboard shortcut!</b></span>"
        )
        # Reset status after 2 seconds
        GLib.timeout_add_seconds(2, self._reset_status_message)

    def on_shortcut_activated(self) -> None:
        """Called when window is shown via keyboard shortcut."""
        self.activation_tracker.increment()
