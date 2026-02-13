#!/usr/bin/env python3
"""
TFCBM DBus Service - Exposes Activate/ShowSettings/Quit over session D-Bus.
"""

import logging
import os
import signal
import subprocess
import traceback
import time

from gi.repository import Gio, GLib

logger = logging.getLogger("TFCBM.DBus")

DBUS_XML = """
<!DOCTYPE node PUBLIC "-//freedesktop//DTD D-BUS Object Introspection 1.0//EN"
"http://www.freedesktop.org/standards/dbus/1.0/introspect.dtd">
<node>
    <interface name="io.github.dyslechtchitect.tfcbm.ClipboardService">
        <method name="Activate">
            <arg type="u" name="timestamp" direction="in"/>
        </method>
        <method name="ShowSettings">
            <arg type="u" name="timestamp" direction="in"/>
        </method>
        <method name="Quit"/>
    </interface>
</node>
"""


class TFCBMDBusService:
    """DBus service exposing Activate / ShowSettings / Quit over session bus."""

    def __init__(self, app):
        """
        Initialize DBus service.

        Args:
            app: The GTK application instance
        """
        self.app = app
        self.connection = None
        self.registration_id = None
        self.bus_name_id = None

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

            # Register object at /io/github/dyslechtchitect/tfcbm/ClipboardService
            self.registration_id = self.connection.register_object(
                "/io/github/dyslechtchitect/tfcbm/ClipboardService",
                interface_info,
                self._handle_method_call,
                None,  # get_property
                None,  # set_property
            )
            logger.info("✓ DBus object registered at /io/github/dyslechtchitect/tfcbm/ClipboardService")

            # Own the bus name io.github.dyslechtchitect.tfcbm.ClipboardService
            # Skip under snap confinement — AppArmor blocks name ownership
            # without a dbus slot, but the object is still callable in-process.
            if not os.environ.get("SNAP"):
                self.bus_name_id = Gio.bus_own_name_on_connection(
                    self.connection,
                    "io.github.dyslechtchitect.tfcbm.ClipboardService",
                    Gio.BusNameOwnerFlags.NONE,
                    None,  # name_acquired_closure
                    None,  # name_lost_closure
                )
                logger.info("✓ Owned D-Bus name io.github.dyslechtchitect.tfcbm.ClipboardService")
            else:
                logger.info("Snap confinement detected, skipping D-Bus name ownership")

            return True

        except Exception as e:
            logger.error(f"Failed to register DBus service: {e}")
            logger.error(traceback.format_exc())
            return False

    def stop(self):
        """Unregister DBus service"""
        if self.connection and self.registration_id:
            self.connection.unregister_object(self.registration_id)
            logger.info("DBus service unregistered")
        if self.bus_name_id:
            Gio.bus_unown_name(self.bus_name_id)
            logger.info("DBus name unowned")

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

    def activate_window(self, activation_token='', timestamp=0):
        """Toggle window visibility. Called directly by portal shortcut or via D-Bus.

        Args:
            activation_token: Wayland activation token from XDG portal (allows focus).
                            Empty string on X11 or when called via external D-Bus.
            timestamp: Portal activation timestamp (used as fallback for focus).
        """
        win = getattr(self.app, 'main_window', None)
        if not win:
            win = getattr(self.app, 'props', None) and self.app.props.active_window

        if win:
            try:
                is_visible = win.is_visible()

                # If recording shortcut and window is visible, do NOT hide it.
                is_recording = getattr(win, 'is_recording_shortcut', False)
                if is_recording and is_visible:
                    logger.info("Ignoring Activate call because shortcut recording is active.")
                    return

                if is_visible and win.is_active():
                    win.hide()
                    if hasattr(win, 'keyboard_handler'):
                        win.keyboard_handler.activated_via_keyboard = False
                    logger.info("Window hidden")
                else:
                    # If portal didn't provide a token, try generating one
                    if not activation_token:
                        activation_token = self._request_activation_token(timestamp)

                    # Set activation token on the GDK display so present()
                    # can use it for Wayland focus via xdg_activation_v1.
                    # Note: os.environ is only read at display init; the GDK
                    # Wayland API must be used at runtime.
                    if activation_token:
                        self._set_activation_token(activation_token)

                    win.show()
                    win.unminimize()
                    win.present()
                    if hasattr(win, 'keyboard_handler'):
                        win.keyboard_handler.activated_via_keyboard = True
                    logger.info("Window shown (token=%s)",
                                'yes' if activation_token else 'no')

                    # Focus first item
                    if hasattr(win, 'keyboard_handler'):
                        GLib.idle_add(win.keyboard_handler.focus_first_item)

            except Exception as e:
                logger.error(f"Error toggling window: {e}")
        else:
            # No window exists yet - activate the app to create it
            if hasattr(self.app, 'activate'):
                GLib.idle_add(self.app.activate)
                logger.info("Activated app to create window")
            else:
                try:
                    result = subprocess.run([
                        'gdbus', 'call', '--session',
                        '--dest', 'io.github.dyslechtchitect.tfcbm',
                        '--object-path', '/io/github/dyslechtchitect/tfcbm',
                        '--method', 'org.gtk.Application.Activate',
                        '{}'
                    ], capture_output=True, timeout=2)
                    if result.returncode == 0:
                        logger.info("Activated UI via org.gtk.Application")
                    else:
                        logger.warning(f"Failed to activate UI: {result.stderr.decode()}")
                except Exception as e:
                    logger.error(f"Error forwarding activate to UI: {e}")

    def _set_activation_token(self, token):
        """Set activation token on the GDK Wayland display for window focus.

        On Wayland, GTK4 reads XDG_ACTIVATION_TOKEN only at display init.
        At runtime we must use the GdkWayland API directly.
        Falls back to env var for X11 / non-Wayland sessions.
        """
        try:
            import gi
            from gi.repository import Gdk
            display = Gdk.Display.get_default()
            if not display:
                os.environ['XDG_ACTIVATION_TOKEN'] = token
                return

            # Import GdkWayland typelib so Wayland-specific methods
            # become available on the display object via GI.
            try:
                gi.require_version('GdkWayland', '4.0')
                from gi.repository import GdkWayland  # noqa: F401
            except (ImportError, ValueError):
                pass

            if hasattr(display, 'set_startup_notification_id'):
                display.set_startup_notification_id(token)
                logger.info("Set Wayland activation token via GdkWayland API")
                return
        except Exception as e:
            logger.debug("GDK Wayland token API unavailable: %s", e)
        # Fallback for X11 or older GTK
        os.environ['XDG_ACTIVATION_TOKEN'] = token

    def _request_activation_token(self, timestamp=0):
        """Generate a Wayland activation token via GDK's app launch context.

        This asks the compositor for an xdg_activation_v1 token that allows
        us to present and focus the window even though the keyboard input
        happened through the portal rather than directly in our app.
        """
        try:
            from gi.repository import Gdk
            display = Gdk.Display.get_default()
            if not display:
                return ''
            context = display.get_app_launch_context()
            if timestamp:
                context.set_timestamp(timestamp)
            token = context.get_startup_notify_id(None, None)
            if token:
                logger.info("Generated fallback activation token via GDK launch context")
                return token
        except Exception as e:
            logger.debug("Could not generate activation token: %s", e)
        return ''

    def _handle_activate(self, parameters, invocation):
        """Handle Activate method from D-Bus - toggle window visibility"""
        timestamp = parameters.unpack()[0] if parameters else 0
        logger.info(f"DBus Activate called with timestamp {timestamp}")
        invocation.return_value(None)
        self.activate_window()

    def _handle_show_settings(self, parameters, invocation):
        """Handle ShowSettings method - show settings page"""
        timestamp = parameters.unpack()[0] if parameters else 0
        logger.info(f"DBus ShowSettings called with timestamp {timestamp}")

        invocation.return_value(None)

        # Try to get window - use main_window reference if available (works even when hidden)
        win = getattr(self.app, 'main_window', None)
        if not win:
            win = getattr(self.app, 'props', None) and self.app.props.active_window

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
            # No window exists yet - activate the show-settings action
            if hasattr(self.app, 'activate_action'):
                # Directly call the app's action
                GLib.idle_add(self.app.activate_action, 'show-settings', None)
                logger.info("Triggered show-settings action directly")
            else:
                # Fallback: trigger show-settings action via D-Bus
                # (This path is for when D-Bus service runs in separate process)
                try:
                    result = subprocess.run([
                        'gdbus', 'call', '--session',
                        '--dest', 'io.github.dyslechtchitect.tfcbm',
                        '--object-path', '/io/github/dyslechtchitect/tfcbm',
                        '--method', 'org.freedesktop.Application.ActivateAction',
                        'show-settings', '[]', '{}'
                    ], capture_output=True, timeout=2)
                    if result.returncode == 0:
                        logger.info("Triggered show-settings action on UI")
                    else:
                        logger.warning(f"Failed to trigger show-settings: {result.stderr.decode()}")
                except Exception as e:
                    logger.error(f"Error forwarding show settings to UI: {e}")

    def _handle_quit(self, invocation):
        """Handle Quit method - quit the application."""
        logger.info("DBus Quit called")

        invocation.return_value(None)

        if hasattr(self.app, 'quit'):
            logger.info("Quitting application - DBus name will be unregistered automatically")
            GLib.idle_add(self.app.quit)
        else:
            # If no app (called from server), send quit to UI via D-Bus
            try:
                # Try to quit the UI gracefully
                result = subprocess.run([
                    'gdbus', 'call', '--session',
                    '--dest', 'io.github.dyslechtchitect.tfcbm',
                    '--object-path', '/io/github/dyslechtchitect/tfcbm',
                    '--method', 'org.freedesktop.Application.ActivateAction',
                    'quit', '[]', '{}'
                ], capture_output=True, timeout=2)
                if result.returncode != 0:
                    # If that didn't work, try killing the UI process
                    subprocess.run(['pkill', '-f', 'ui/main.py'], timeout=2)
                logger.info("Quit command sent to UI")
            except Exception as e:
                logger.error(f"Error forwarding quit to UI: {e}")

