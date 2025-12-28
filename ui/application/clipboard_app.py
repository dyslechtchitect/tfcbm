"""Main TFCBM application."""

import logging
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GdkPixbuf", "2.0")

from gi.repository import Adw, Gdk, GdkPixbuf, Gio, GLib, Gtk

# Add parent directory to path to import server modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from server.src.dbus_service import TFCBMDBusService

logger = logging.getLogger("TFCBM.UI")


class ClipboardApp(Adw.Application):
    """Main application"""

    def __init__(self, server_pid=None):
        super().__init__(
            application_id="org.tfcbm.ClipboardManager",
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
        )
        self.server_pid = server_pid
        self.dbus_service = None
        self.splash_window = None
        self.main_window = None  # Track main window even when hidden

        self.add_main_option(
            "activate",
            ord("a"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            "Activate and bring window to front",
            None,
        )
        self.add_main_option(
            "server-pid",
            ord("s"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.INT,
            "Server process ID to monitor",
            "PID",
        )

    def do_startup(self):
        """Application startup - set icon"""
        Adw.Application.do_startup(self)

        # Set the default icon name for the application
        # This tells GNOME Shell which icon to use from the icon theme
        Gtk.Window.set_default_icon_name("org.tfcbm.ClipboardManager")

        try:
            css_path = Path(__file__).parent.parent / "style.css"
            if css_path.exists():
                provider = Gtk.CssProvider()
                provider.load_from_path(str(css_path))
                Gtk.StyleContext.add_provider_for_display(
                    Gdk.Display.get_default(),
                    provider,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
                )
                print(f"Loaded custom CSS from {css_path}")
        except Exception as e:
            print(f"Warning: Could not load custom CSS: {e}")

        # Register D-Bus service for extension integration
        # The UI handles Activate/ShowSettings/Quit commands AND forwards clipboard events to server
        self.dbus_service = TFCBMDBusService(self, clipboard_handler=self._handle_clipboard_event)
        self.dbus_service.start()

        # Register actions for tray icon integration
        activate_action = Gio.SimpleAction.new("show-window", None)
        activate_action.connect("activate", self._on_show_window_action)
        self.add_action(activate_action)

        # Add show-settings action for tray icon integration
        settings_action = Gio.SimpleAction.new("show-settings", None)
        settings_action.connect("activate", self._on_show_settings_action)
        self.add_action(settings_action)

        # Add quit action for tray icon integration
        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", self._on_quit_action)
        self.add_action(quit_action)

    def _handle_clipboard_event(self, event_data):
        """Forward clipboard events from GNOME extension to the server"""
        import asyncio
        import websockets
        import json

        async def send_to_server():
            try:
                async with websockets.connect('ws://localhost:8765') as websocket:
                    await websocket.send(json.dumps({
                        'action': 'clipboard_event',
                        'data': event_data
                    }))
                    logger.info(f"Forwarded {event_data.get('type')} event to server")
            except Exception as e:
                logger.error(f"Failed to forward clipboard event to server: {e}")

        # Run async task
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(send_to_server())
        except Exception as e:
            logger.error(f"Error handling clipboard event in UI: {e}")

    def _on_show_window_action(self, action, parameter):
        """Handle show-window action"""
        logger.info("show-window action triggered")
        self.activate()

    def _on_show_settings_action(self, action, parameter):
        """Handle show-settings action - show window and navigate to settings"""
        logger.info("show-settings action triggered")
        # Use stored main_window reference (works even when hidden)
        win = self.main_window if self.main_window else self.props.active_window

        if not win:
            # Create window first
            self.activate()
            win = self.main_window if self.main_window else self.props.active_window

        if win:
            # Show and present window
            win.show()
            win.unminimize()
            win.present()
            # Navigate to settings page
            if hasattr(win, '_show_settings_page'):
                GLib.idle_add(win._show_settings_page, None)

    def _on_quit_action(self, action, parameter):
        """Handle quit action"""
        logger.info("quit action triggered")
        self.quit()

    def do_command_line(self, command_line):
        """Handle command-line arguments"""
        options = command_line.get_options_dict()
        options = options.end().unpack()

        if "server-pid" in options:
            self.server_pid = options["server-pid"]
            logger.info(f"Monitoring server PID: {self.server_pid}")

        if "activate" in options:
            self.activate()
        else:
            self.activate()

        return 0

    def do_activate(self):
        """Activate the application - toggle window visibility"""
        # Use stored main_window reference (works even when hidden)
        win = self.main_window if self.main_window else self.props.active_window

        if not win:
            # Show splash screen first
            self._show_splash()

            # Load main window in background
            GLib.timeout_add(100, self._load_main_window)
        else:
            # Toggle window visibility instead of always showing
            logger.info("Toggling window visibility...")
            if win.is_visible():
                logger.info("Hiding window")
                win.hide()
                if hasattr(win, 'keyboard_handler'):
                    win.keyboard_handler.activated_via_keyboard = False
            else:
                logger.info("Showing window")
                win.show()
                win.unminimize()
                win.present()
                if hasattr(win, 'keyboard_handler'):
                    win.keyboard_handler.activated_via_keyboard = True
                    # Focus first item
                    GLib.idle_add(win.keyboard_handler.focus_first_item)

    def _show_splash(self):
        """Show splash screen"""
        from ui.splash import SplashWindow

        if not self.splash_window:
            self.splash_window = SplashWindow()
            self.splash_window.set_application(self)
            self.splash_window.present()
            logger.info("Splash screen displayed")

    def _load_main_window(self):
        """Load main window (called after splash is shown)"""
        try:
            # Check if GNOME extension is ready (installed AND enabled)
            from ui.utils.extension_check import get_extension_status, enable_extension

            ext_status = get_extension_status()

            # Only show setup screen if extension is NOT installed
            if not ext_status['installed']:
                logger.warning("GNOME extension not installed - showing setup window")
                from ui.windows.extension_error_window import ExtensionErrorWindow

                # Close splash
                self._close_splash()

                error_win = ExtensionErrorWindow(self, ext_status)
                error_win.present()
                return False

            # If extension is installed but not enabled, auto-enable it
            if ext_status['installed'] and not ext_status['enabled']:
                logger.info("Extension installed but not enabled - auto-enabling...")
                success, message = enable_extension()
                if success:
                    logger.info("Extension auto-enabled successfully")
                else:
                    logger.warning(f"Failed to auto-enable extension: {message}")

            # Extension is installed (and now enabled or will be), proceed with normal window
            from ui.windows.clipboard_window import ClipboardWindow

            win = ClipboardWindow(self, self.server_pid)
            self.main_window = win  # Store reference for later use

            # Show window on first launch
            win.present()

            # Close splash once main window is ready
            self._close_splash()

            logger.info("Main window loaded and presented")
        except Exception as e:
            logger.error(f"Error loading main window: {e}")
            self._close_splash()

        return False  # Don't repeat timeout

    def _close_splash(self):
        """Close splash screen"""
        if self.splash_window:
            self.splash_window.close()
            self.splash_window = None
            logger.info("Splash screen closed")


def main():
    """Entry point"""
    import signal

    logger.info("TFCBM UI starting...")

    def signal_handler(sig, frame):
        print("Shutting down UI...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    app = ClipboardApp()
    try:
        return app.run(sys.argv)
    except KeyboardInterrupt:
        print("\n\nShutting down UI...")
        sys.exit(0)


if __name__ == "__main__":
    main()
