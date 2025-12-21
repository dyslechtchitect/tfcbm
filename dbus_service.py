#!/usr/bin/env python3
"""
TFCBM DBus Service - Handles DBus communication for GNOME extension integration
"""

import json
import logging
from gi.repository import Gio, GLib

logger = logging.getLogger("TFCBM.DBus")

DBUS_XML = """
<!DOCTYPE node PUBLIC "-//freedesktop//DTD D-BUS Object Introspection 1.0//EN"
"http://www.freedesktop.org/standards/dbus/1.0/introspect.dtd">
<node>
    <interface name="org.tfcbm.ClipboardManager">
        <method name="Activate">
            <arg type="u" name="timestamp" direction="in"/>
        </method>
        <method name="ShowSettings">
            <arg type="u" name="timestamp" direction="in"/>
        </method>
        <method name="Quit"/>
        <method name="OnClipboardChange">
            <arg type="s" name="eventData" direction="in"/>
        </method>
    </interface>
</node>
"""


class TFCBMDBusService:
    """DBus service for TFCBM integration with GNOME extension"""

    def __init__(self, app, clipboard_handler=None):
        """
        Initialize DBus service

        Args:
            app: The GTK application instance
            clipboard_handler: Callback function to handle clipboard events
                              Should accept (event_data: dict) -> None
        """
        self.app = app
        self.clipboard_handler = clipboard_handler
        self.connection = None
        self.registration_id = None

    def start(self):
        """Register DBus service"""
        try:
            # Get session bus connection
            if hasattr(self.app, 'get_dbus_connection'):
                # If app is a Gio.Application
                self.connection = self.app.get_dbus_connection()
            else:
                # Otherwise get session bus directly
                self.connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)

            if not self.connection:
                logger.error("Failed to get DBus connection")
                return False

            # Parse DBus interface
            node_info = Gio.DBusNodeInfo.new_for_xml(DBUS_XML)
            interface_info = node_info.interfaces[0]

            # Register object
            self.registration_id = self.connection.register_object(
                "/org/tfcbm/ClipboardManager",
                interface_info,
                self._handle_method_call,
                None,  # get_property
                None,  # set_property
            )

            logger.info("✓ DBus service registered at org.tfcbm.ClipboardManager")
            return True

        except Exception as e:
            logger.error(f"Failed to register DBus service: {e}")
            return False

    def stop(self):
        """Unregister DBus service"""
        if self.connection and self.registration_id:
            self.connection.unregister_object(self.registration_id)
            logger.info("DBus service unregistered")

    def _handle_method_call(
        self,
        connection,
        sender,
        object_path,
        interface_name,
        method_name,
        parameters,
        invocation,
    ):
        """Handle incoming DBus method calls"""
        try:
            if method_name == "Activate":
                self._handle_activate(parameters, invocation)

            elif method_name == "ShowSettings":
                self._handle_show_settings(parameters, invocation)

            elif method_name == "Quit":
                self._handle_quit(invocation)

            elif method_name == "OnClipboardChange":
                self._handle_clipboard_change(parameters, invocation)

            else:
                invocation.return_error_literal(
                    Gio.io_error_quark(),
                    Gio.IOErrorEnum.NOT_SUPPORTED,
                    f"Method {method_name} not supported",
                )

        except Exception as e:
            logger.error(f"Error handling DBus call {method_name}: {e}")
            invocation.return_error_literal(
                Gio.io_error_quark(),
                Gio.IOErrorEnum.FAILED,
                str(e),
            )

    def _handle_activate(self, parameters, invocation):
        """Handle Activate method - toggle window visibility"""
        timestamp = parameters.unpack()[0] if parameters else 0
        logger.info(f"DBus Activate called with timestamp {timestamp}")

        # Return immediately to avoid blocking the caller
        invocation.return_value(None)

        # Get active window
        win = self.app.props.active_window
        if win:
            try:
                is_visible = win.is_visible()

                if is_visible:
                    win.hide()
                    if hasattr(win, 'keyboard_handler'):
                        win.keyboard_handler.activated_via_keyboard = False
                    logger.info("Window hidden via DBus")
                else:
                    win.show()
                    win.unminimize()
                    win.present_with_time(timestamp)
                    if hasattr(win, 'keyboard_handler'):
                        win.keyboard_handler.activated_via_keyboard = True
                    logger.info("Window shown via DBus")

                    # Focus first item
                    if hasattr(win, 'keyboard_handler'):
                        GLib.idle_add(win.keyboard_handler.focus_first_item)

            except Exception as e:
                logger.error(f"Error toggling window: {e}")
        else:
            logger.warning("No active window to activate")

    def _handle_show_settings(self, parameters, invocation):
        """Handle ShowSettings method - show settings page"""
        timestamp = parameters.unpack()[0] if parameters else 0
        logger.info(f"DBus ShowSettings called with timestamp {timestamp}")

        invocation.return_value(None)

        win = self.app.props.active_window
        if win:
            try:
                # Show window if hidden
                if not win.is_visible():
                    win.show()
                    win.unminimize()
                    win.present_with_time(timestamp)

                # Navigate to settings page
                if hasattr(win, '_show_settings_page'):
                    GLib.idle_add(win._show_settings_page, None)
                    logger.info("Navigated to settings page via DBus")
                else:
                    logger.warning("Window doesn't have _show_settings_page method")

            except Exception as e:
                logger.error(f"Error showing settings: {e}")
        else:
            logger.warning("No active window to show settings")

    def _handle_quit(self, invocation):
        """Handle Quit method - quit the application"""
        logger.info("DBus Quit called")

        invocation.return_value(None)

        # Quit the application
        GLib.idle_add(self.app.quit)
        logger.info("Application quit requested via DBus")

    def _handle_clipboard_change(self, parameters, invocation):
        """Handle OnClipboardChange method - process clipboard event from extension"""
        event_data_json = parameters.unpack()[0]
        logger.debug(f"DBus OnClipboardChange called with data: {event_data_json[:100]}...")

        # Return immediately to avoid blocking the extension
        invocation.return_value(None)

        try:
            # Parse event data
            event_data = json.loads(event_data_json)

            # Call clipboard handler if provided
            if self.clipboard_handler:
                self.clipboard_handler(event_data)
            else:
                logger.warning("No clipboard handler registered, event ignored")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse clipboard event JSON: {e}")
        except Exception as e:
            logger.error(f"Error processing clipboard event: {e}")
