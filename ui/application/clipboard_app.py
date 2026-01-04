"""Main TFCBM application."""

import asyncio
import logging
import os
import sys
import threading
import time
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GdkPixbuf", "2.0")

from gi.repository import Adw, Gdk, GdkPixbuf, Gio, GLib, Gtk

# Add parent directory to path to import server modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from server.src.dbus_service import TFCBMDBusService
from server.src.services.settings_service import SettingsService
from server.src.services.database_service import DatabaseService
from server.src.services.thumbnail_service import ThumbnailService
from server.src.services.clipboard_service import ClipboardService
from server.src.services.ipc_service import IPCService

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

        # Initialize backend services for IPC
        self.settings_service = SettingsService()
        self.database_service = DatabaseService(settings_service=self.settings_service)
        self.thumbnail_service = ThumbnailService(self.database_service)
        self.clipboard_service = ClipboardService(self.database_service, self.thumbnail_service)
        self.ipc_service = IPCService(
            self.database_service,
            self.settings_service,
            self.clipboard_service
        )
        self.ipc_thread = None
        self.ipc_loop = None

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
        logger.info("Starting DBus service...")
        self.dbus_service = TFCBMDBusService(self, clipboard_handler=self._handle_clipboard_event)
        self.dbus_service.start()
        logger.info("✓ DBus service registered")

        # Start IPC server for side panel mode
        logger.info("About to start IPC server...")
        try:
            self._start_ipc_server()
            logger.info("✓ IPC server start method completed")
        except Exception as e:
            logger.error(f"Failed to start IPC server: {e}", exc_info=True)

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
        """Process clipboard events from GNOME extension and save to database"""
        try:
            logger.info(f"Received clipboard event: {event_data.get('type')}")

            # Use existing clipboard service to save the item
            self.clipboard_service.handle_clipboard_event(event_data)

            # The database watcher will detect the new item and broadcast via IPC
            # No need to manually broadcast here

        except Exception as e:
            logger.error(f"Error processing clipboard event: {e}", exc_info=True)

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
        self._stop_ipc_server()
        self.quit()

    async def _start_ipc_server_async(self):
        """Start UNIX domain socket IPC server for side panel"""
        logger.info("=== _start_ipc_server_async called ===")
        socket_path = self.ipc_service.socket_path
        socket_dir = os.path.dirname(socket_path)
        logger.info(f"Socket path: {socket_path}")
        logger.info(f"Socket dir: {socket_dir}")

        # Create socket directory if it doesn't exist
        logger.info("Creating socket directory...")
        os.makedirs(socket_dir, mode=0o700, exist_ok=True)
        logger.info("Socket directory created/verified")

        # Remove existing socket if it exists
        try:
            if os.path.exists(socket_path):
                logger.info("Removing existing socket...")
                os.unlink(socket_path)
                logger.info(f"Removed existing socket at {socket_path}")
        except (FileNotFoundError, OSError) as e:
            logger.warning(f"Could not remove existing socket: {e}")
            # Try to continue anyway - the socket might be stale

        logger.info(f"Starting IPC server on {socket_path}")
        try:
            logger.info("Calling asyncio.start_unix_server...")
            server = await asyncio.start_unix_server(
                self.ipc_service.client_handler,
                socket_path
            )
            logger.info("Server created successfully")

            # Set socket permissions to allow only user access
            logger.info("Setting socket permissions...")
            os.chmod(socket_path, 0o600)
            logger.info("Socket permissions set to 0600")

            logger.info("✓ IPC server listening")
            logger.info("Entering server.serve_forever()...")
            async with server:
                await server.serve_forever()
            logger.info("serve_forever() exited")
        except OSError as e:
            logger.error(f"Failed to start IPC server (OSError): {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Failed to start IPC server (unexpected): {e}", exc_info=True)
            raise

    def _watch_for_new_items(self, loop):
        """Watch database for new items and broadcast to IPC clients"""
        logger.info("Started database watcher")

        while True:
            try:
                latest_id = self.database_service.get_latest_id()

                if latest_id and latest_id > self.ipc_service.last_known_id:
                    # New items detected
                    logger.info(f"📢 Broadcasting new items {self.ipc_service.last_known_id + 1} to {latest_id}")
                    for item_id in range(self.ipc_service.last_known_id + 1, latest_id + 1):
                        item = self.database_service.get_item(item_id)
                        if item:
                            ui_item = self.ipc_service.prepare_item_for_ui(item)

                            # Broadcast to all clients
                            message = {"type": "new_item", "item": ui_item}

                            # Schedule broadcast in async loop
                            asyncio.run_coroutine_threadsafe(
                                self.ipc_service.broadcast(message),
                                loop
                            )
                            logger.info(f"  → Broadcast item {item_id} ({item['type']}) to {len(self.ipc_service.clients)} clients")

                    self.ipc_service.last_known_id = latest_id

            except Exception as e:
                logger.error(f"Error in database watcher: {e}")

            time.sleep(0.5)

    def _start_ipc_server(self):
        """Start IPC server in background thread"""
        logger.info("=== _start_ipc_server called ===")
        try:
            logger.info("Starting IPC server thread...")

            def run_ipc_server():
                try:
                    logger.info("IPC server thread running...")
                    self.ipc_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(self.ipc_loop)
                    logger.info("Event loop created")

                    # Start database watcher
                    logger.info("Starting database watcher...")
                    watcher_thread = threading.Thread(
                        target=self._watch_for_new_items,
                        args=(self.ipc_loop,),
                        daemon=True
                    )
                    watcher_thread.start()
                    logger.info("Database watcher started")

                    # Start IPC server and keep event loop running forever
                    logger.info("Creating IPC server task...")
                    # Create the server task
                    self.ipc_loop.create_task(self._start_ipc_server_async())
                    logger.info("Running event loop forever...")
                    # Run the event loop forever (doesn't wait for server to complete)
                    self.ipc_loop.run_forever()
                    logger.info("Event loop stopped")
                except Exception as e:
                    logger.error(f"Error in IPC server thread: {e}", exc_info=True)

            logger.info("Creating IPC thread...")
            self.ipc_thread = threading.Thread(target=run_ipc_server, daemon=True)
            logger.info("Starting IPC thread...")
            self.ipc_thread.start()
            logger.info("IPC server thread started")
        except Exception as e:
            logger.error(f"Error starting IPC server: {e}", exc_info=True)

    def _stop_ipc_server(self):
        """Stop IPC server and clean up socket"""
        try:
            if self.ipc_loop:
                self.ipc_loop.call_soon_threadsafe(self.ipc_loop.stop)

            # Clean up IPC socket
            socket_path = self.ipc_service.socket_path
            if os.path.exists(socket_path):
                os.unlink(socket_path)
                logger.info("IPC socket removed")
        except Exception as e:
            logger.error(f"Error stopping IPC server: {e}")

    def do_command_line(self, command_line):
        """Handle command-line arguments"""
        options = command_line.get_options_dict()
        options = options.end().unpack()

        if "server-pid" in options:
            self.server_pid = options["server-pid"]
            logger.info(f"Monitoring server PID: {self.server_pid}")

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
        # ALWAYS check extension status first, regardless of UI mode
        from ui.utils.extension_check import get_extension_status, enable_extension

        ext_status = get_extension_status()

        # If extension not installed OR not enabled, show the install/enable window
        # This happens BEFORE we check UI mode
        if not ext_status['installed'] or not ext_status['enabled']:
            logger.warning(f"Extension not ready - installed: {ext_status['installed']}, enabled: {ext_status['enabled']}")
            from ui.windows.extension_error_window import ExtensionErrorWindow
            error_win = ExtensionErrorWindow(self, ext_status)
            error_win.present()
            return

        # Extension is installed AND enabled - now check UI mode
        if self.settings_service.ui_mode == 'sidepanel':
            logger.info("Extension ready and in sidepanel mode - running in background")
            self.hold()
            return

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

    def do_shutdown(self):
        """Application shutdown - cleanup IPC server"""
        logger.info("Application shutting down...")
        self._stop_ipc_server()
        Adw.Application.do_shutdown(self)


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
