"""Main TFCBM application."""

import logging
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GdkPixbuf", "2.0")

from gi.repository import Adw, Gdk, GdkPixbuf, Gio, GLib, Gtk

# Add parent directory to path to import dbus_service
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from dbus_service import TFCBMDBusService

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

        try:
            icon_path = (
                Path(__file__).parent.parent.parent / "resouces" / "icon.svg"
            )
            if icon_path.exists():
                # Add the icon directory to the icon theme search path
                display = Gdk.Display.get_default()
                if display:
                    icon_theme = Gtk.IconTheme.get_for_display(display)
                    icon_theme.add_search_path(str(icon_path.parent))

                    # Copy the icon with the application ID name so GTK can find it
                    import shutil
                    app_icon_path = icon_path.parent / "org.tfcbm.ClipboardManager.svg"
                    if not app_icon_path.exists():
                        shutil.copy(icon_path, app_icon_path)

                    print(f"Set up application icon at {icon_path}")
        except Exception as e:
            print(f"Warning: Could not set up application icon: {e}")

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

    def _on_show_window_action(self, action, parameter):
        """Handle show-window action"""
        logger.info("show-window action triggered")
        self.activate()

    def _on_show_settings_action(self, action, parameter):
        """Handle show-settings action - show window and navigate to settings"""
        logger.info("show-settings action triggered")
        win = self.props.active_window
        if not win:
            # Create window first
            self.activate()
            win = self.props.active_window

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
        win = self.props.active_window
        if not win:
            from ui.windows.clipboard_window import ClipboardWindow

            win = ClipboardWindow(self, self.server_pid)
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
