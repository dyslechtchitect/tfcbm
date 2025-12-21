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
                pixbuf = GdkPixbuf.Pixbuf.new_from_file(str(icon_path))
                Gdk.Texture.new_for_pixbuf(pixbuf)
                display = Gdk.Display.get_default()
                if display:
                    icon_theme = Gtk.IconTheme.get_for_display(display)
                    icon_theme.add_search_path(str(icon_path.parent))
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

        # Setup DBus service using the new modular service
        self.dbus_service = TFCBMDBusService(self)
        self.dbus_service.start()

        activate_action = Gio.SimpleAction.new("show-window", None)
        activate_action.connect("activate", self._on_show_window_action)
        self.add_action(activate_action)

    def _on_show_window_action(self, action, parameter):
        """Handle show-window action"""
        logger.info("show-window action triggered")
        self.activate()

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
        """Activate the application"""
        win = self.props.active_window
        if not win:
            from ui.windows.clipboard_window import ClipboardWindow

            win = ClipboardWindow(self, self.server_pid)
        else:
            logger.info("Activating existing window...")
            win.present()
            logger.info("Window activation requested")


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
