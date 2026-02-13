"""Main TFCBM application - DE-agnostic version using GTK4."""

import logging
import sys
from pathlib import Path
from ui.windows.license_window import LicenseWindow
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("GdkPixbuf", "2.0")

from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk

# Add parent directory to path to import server modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from server.src.dbus_service import TFCBMDBusService

logger = logging.getLogger("TFCBM.UI")


class ClipboardApp(Gtk.Application):
    """Main application"""

    def __init__(self, server_pid=None):
        super().__init__(
            application_id="io.github.dyslechtchitect.tfcbm",
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
        )
        self.server_pid = server_pid
        self.dbus_service = None
        self.splash_window = None
        self.main_window = None  # Track main window even when hidden
        self.clipboard_monitor = None
        self.shortcut_listener = None

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
        # Optionally initialize libadwaita for native GNOME styling.
        # Falls back to plain GTK4 theming on DEs without libadwaita.
        try:
            gi.require_version("Adw", "1")
            from gi.repository import Adw
            Adw.init()
            Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.DEFAULT)
        except (ImportError, ValueError):
            pass

        Gtk.Application.do_startup(self)

        # Set the default icon name for the application
        Gtk.Window.set_default_icon_name("io.github.dyslechtchitect.tfcbm")

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

        # Register D-Bus service (Activate / ShowSettings / Quit)
        self.dbus_service = TFCBMDBusService(self)
        if not self.dbus_service.start():
            logger.error("Failed to start DBus service")

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
        """Forward clipboard events to the server"""
        import asyncio
        from ui.services.ipc_helpers import connect as ipc_connect
        import json

        async def send_to_server():
            try:
                async with ipc_connect() as conn:
                    await conn.send(json.dumps({
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

    def _start_clipboard_monitor(self):
        """Start the DE-agnostic clipboard monitor."""
        if self.clipboard_monitor:
            return  # Already running

        from ui.services.clipboard_monitor import ClipboardMonitor
        self.clipboard_monitor = ClipboardMonitor(
            on_clipboard_event=self._handle_clipboard_event
        )
        self.clipboard_monitor.start()
        logger.info("Clipboard monitor started")

    def _stop_clipboard_monitor(self):
        """Stop the clipboard monitor."""
        if self.clipboard_monitor:
            self.clipboard_monitor.stop()
            self.clipboard_monitor = None
            logger.info("Clipboard monitor stopped")

    def _start_shortcut_listener(self):
        """Start the XDG GlobalShortcuts portal listener in-process."""
        if self.shortcut_listener:
            return
        from ui.services.shortcut_listener import ShortcutListener
        self.shortcut_listener = ShortcutListener(on_activated=self._on_shortcut_activated)
        self.shortcut_listener.start()
        logger.info("Shortcut listener started")

    def _on_shortcut_activated(self, activation_token='', timestamp=0):
        """Handle portal shortcut activation with activation token for Wayland focus."""
        if self.dbus_service:
            self.dbus_service.activate_window(activation_token, timestamp)
        else:
            logger.warning("No dbus_service available for shortcut activation")

    def _stop_shortcut_listener(self):
        """Stop the shortcut listener."""
        if self.shortcut_listener:
            self.shortcut_listener.stop()
            self.shortcut_listener = None
            logger.info("Shortcut listener stopped")

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
        self._cleanup_server()
        logging.shutdown() # Ensure logs are flushed
        self.quit()

    def do_shutdown(self):
        """Called when application is shutting down - cleanup"""
        logger.info("Application shutting down")

        self._stop_shortcut_listener()
        self._stop_clipboard_monitor()

        self._cleanup_server()
        Gtk.Application.do_shutdown(self)

    def _cleanup_server(self):
        """Request graceful shutdown of server via IPC"""
        print(f"[CLEANUP] _cleanup_server called")
        logger.info("Requesting server shutdown via IPC")

        try:
            import asyncio
            import json
            from ui.services.ipc_helpers import connect as ipc_connect

            async def send_shutdown():
                try:
                    print(f"[CLEANUP] Connecting to IPC server to send shutdown")
                    async with ipc_connect() as conn:
                        print(f"[CLEANUP] Sending shutdown request")
                        request = {"action": "shutdown"}
                        await conn.send(json.dumps(request))

                        print(f"[CLEANUP] Waiting for acknowledgment (timeout: 1s)")
                        # Use wait_for with timeout to avoid hanging if server already died
                        response = await asyncio.wait_for(conn.recv(), timeout=1.0)
                        data = json.loads(response)

                        if data.get("type") == "shutdown_acknowledged":
                            print(f"[CLEANUP] Server acknowledged shutdown")
                            logger.info("Server acknowledged shutdown request")
                        else:
                            print(f"[CLEANUP] Unexpected response: {data}")
                except asyncio.TimeoutError:
                    print(f"[CLEANUP] Timeout waiting for acknowledgment (server may have already exited)")
                except Exception as e:
                    print(f"[CLEANUP] Error sending shutdown via IPC: {e}")
                    logger.error(f"Error sending shutdown via IPC: {e}")

            # Run the shutdown request
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(send_shutdown())
            finally:
                loop.close()
                print(f"[CLEANUP] Shutdown request completed")

        except Exception as e:
            print(f"[CLEANUP] Error during cleanup: {e}")
            logger.error(f"Error during cleanup: {e}")

    def do_command_line(self, command_line):
        """Handle command-line arguments"""
        options = command_line.get_options_dict()
        options = options.end().unpack()
        logger.info(f"do_command_line received options: {options}")

        if "server-pid" in options:
            self.server_pid = options["server-pid"]

        # Only activate (show window) if explicitly requested via --activate flag
        # Otherwise, just run in background with DBus service + tray icon
        if "activate" in options:
            logger.info("--activate flag detected, showing window")
            self.activate()
        else:
            logger.info("Starting in background mode (no --activate flag)")
            # Keep the application running but don't show window
            # The DBus service and tray icon will handle window activation
            self.hold()

        return 0

    def _settings_path(self):
        """Return the canonical settings file path (same as JsonSettingsStore)."""
        import os
        config_home = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
        return Path(config_home) / "tfcbm" / "settings.json"

    def do_activate(self):
        """Activate the application - toggle window visibility"""

        # Check if license has already been accepted
        import json

        settings_path = self._settings_path()
        license_accepted = False

        try:
            if settings_path.exists():
                with open(settings_path, 'r') as f:
                    settings = json.load(f)
                    license_accepted = settings.get('license_accepted', False)
        except Exception as e:
            logger.error(f"Error loading license status: {e}")

        if license_accepted:
            # License already accepted, proceed directly
            logger.info("License already accepted, proceeding with activation")
            self._proceed_with_activation()
        else:
            # Show license window for first-time users
            logger.info("Showing license window for first-time acceptance")
            license_win = LicenseWindow(callback=self._on_license_response)
            license_win.set_application(self)
            license_win.present()

    def _on_license_response(self, accepted):
        """Handle license window response"""
        logger.info(f"License response: accepted={accepted}")
        if accepted:
            # Save license acceptance to settings
            self._save_license_acceptance()
            self._proceed_with_activation()
        else:
            logger.info("License not accepted. Quitting application.")
            self.quit()

    def _save_license_acceptance(self):
        """Save license acceptance status to settings.json"""
        import json

        settings_path = self._settings_path()

        try:
            # Load existing settings or create new
            settings = {}
            if settings_path.exists():
                with open(settings_path, 'r') as f:
                    settings = json.load(f)

            # Update license acceptance
            settings['license_accepted'] = True

            # Ensure parent directory exists
            settings_path.parent.mkdir(parents=True, exist_ok=True)

            # Save settings
            with open(settings_path, 'w') as f:
                json.dump(settings, f, indent=2)

            logger.info(f"License acceptance saved to {settings_path}")
        except Exception as e:
            logger.error(f"Error saving license acceptance: {e}")

    def _proceed_with_activation(self):
        logger.info("DEBUG: _proceed_with_activation called")
        # Only use stored main_window reference (don't use active_window as it might be the license window)
        win = self.main_window
        logger.info(f"DEBUG: main_window={self.main_window}")

        if not win:
            logger.info("DEBUG: No main window exists, creating new one")
            # Show splash screen first
            self._show_splash()

            # Load main window in background
            GLib.timeout_add(100, self._load_main_window)
        else:
            logger.info("DEBUG: Main window exists, showing it")
            # Window already exists, just show it
            win.show()
            win.unminimize()
            win.present()


    def _show_splash(self):
        """Show splash screen"""
        logger.info("DEBUG: Entering _show_splash")
        from ui.splash import SplashWindow

        if not self.splash_window:
            self.splash_window = SplashWindow()
            self.splash_window.set_application(self)
            self.splash_window.present()
            logger.info("Splash screen displayed")
            logger.info("DEBUG: Splash screen presented.")

    def _load_main_window(self):
        """Load main window (called after splash is shown)"""
        logger.info("DEBUG: Entering _load_main_window")
        try:
            # No extension check needed - we use built-in clipboard monitoring
            logger.info("Loading main window (no extension required)")
            from ui.windows.clipboard_window import ClipboardWindow

            win = ClipboardWindow(self, self.server_pid)
            self.main_window = win  # Store reference for later use

            # Show window on first launch
            win.present()
            logger.info("DEBUG: Main window presented.")

            # Close splash once main window is ready
            self._close_splash()

            # Start clipboard monitoring (replaces GNOME extension monitoring)
            self._start_clipboard_monitor()

            # Defer shortcut listener to after the window is fully realized.
            # The portal may need to show a system dialog on first bind, which
            # requires the app and main loop to be fully up and running.
            GLib.idle_add(self._start_shortcut_listener)

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
