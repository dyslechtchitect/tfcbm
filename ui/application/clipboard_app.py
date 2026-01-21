"""Main TFCBM application."""

import logging
import sys
from pathlib import Path
from ui.windows.license_window import LicenseWindow
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
            application_id="io.github.dyslechtchitect.tfcbm",
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

        # Register D-Bus service for extension integration
        # The UI handles Activate/ShowSettings/Quit commands AND forwards clipboard events to server
        self.dbus_service = TFCBMDBusService(self, clipboard_handler=self._handle_clipboard_event)
        if not self.dbus_service.start():
            logger.error("Failed to start DBus service - extension integration may not work")

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
        """Called when application is shutting down - cleanup server"""
        logger.info("Application shutting down")

        # Stop clipboard monitoring and disable keybinding in the extension
        logger.info("Stopping clipboard monitoring and disabling keybinding in extension...")
        try:
            from ui.infrastructure.gsettings_store import ExtensionSettingsStore
            settings_store = ExtensionSettingsStore()

            monitoring_stopped = settings_store.stop_monitoring()
            keybinding_disabled = settings_store.disable_keybinding()

            if monitoring_stopped and keybinding_disabled:
                logger.info("✓ Clipboard monitoring stopped and keybinding disabled")
            elif monitoring_stopped:
                logger.warning("Monitoring stopped but keybinding failed to disable")
            else:
                logger.warning("Failed to stop clipboard monitoring")
        except Exception as e:
            logger.warning(f"Error stopping monitoring/keybinding: {e}")

        self._cleanup_server()
        Adw.Application.do_shutdown(self)

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
        logger.info(f"do_command_line received options: {options}") # <-- Retain this one
        # Removed: logger.info(f"command_line arguments: {[arg.get_string() for arg in command_line.get_arguments()]}")

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

    def do_activate(self):
        """Activate the application - toggle window visibility"""

        # Check if license has already been accepted
        import json
        from pathlib import Path

        settings_path = Path.home() / ".var/app/io.github.dyslechtchitect.tfcbm/config/settings.json"
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
        from pathlib import Path

        settings_path = Path.home() / ".var/app/io.github.dyslechtchitect.tfcbm/config/settings.json"

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

    def _load_main_window(self, skip_extension_check=False):
        """Load main window (called after splash is shown)"""
        logger.info("DEBUG: Entering _load_main_window")
        try:
            # Check if GNOME extension is ready (installed AND enabled)
            from ui.utils.extension_check import get_extension_status, enable_extension

            if not skip_extension_check:
                logger.info("Checking GNOME extension status...")
                ext_status = get_extension_status()
                logger.info(f"Extension status: {ext_status}")
            else:
                logger.info("Skipping extension check (already verified)")
                ext_status = {'installed': True, 'ready': True}

            # Show setup screen if extension is not installed OR not ready (needs enabling)
            if not ext_status['installed'] or not ext_status['ready']:
                if not ext_status['installed']:
                    logger.warning("GNOME extension not installed - showing setup window")
                else:
                    logger.warning("GNOME extension installed but not ready (needs enabling) - showing setup window")

                from ui.windows.extension_error_window import ExtensionErrorWindow

                # Close splash
                self._close_splash()

                error_win = ExtensionErrorWindow(self, ext_status)
                error_win.present()
                logger.info("ExtensionErrorWindow displayed.")
                logger.info("DEBUG: Error window presented.")
                return False

            # Extension is installed, proceed with normal window
            logger.info("Extension is ready. Proceeding to load main window.")
            from ui.windows.clipboard_window import ClipboardWindow

            win = ClipboardWindow(self, self.server_pid)
            self.main_window = win  # Store reference for later use

            # Show window on first launch
            win.present()
            logger.info("DEBUG: Main window presented.")

            # Close splash once main window is ready
            self._close_splash()

            # Start clipboard monitoring and enable keybinding in the extension
            logger.info("Starting clipboard monitoring and enabling keybinding in extension...")
            from ui.infrastructure.gsettings_store import ExtensionSettingsStore
            settings_store = ExtensionSettingsStore()

            monitoring_started = settings_store.start_monitoring()
            keybinding_enabled = settings_store.enable_keybinding()

            if monitoring_started and keybinding_enabled:
                logger.info("✓ Clipboard monitoring started and keybinding enabled")
            elif monitoring_started:
                logger.warning("Monitoring started but keybinding failed to enable")
            else:
                logger.warning("Failed to start clipboard monitoring - extension may not be ready")

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
