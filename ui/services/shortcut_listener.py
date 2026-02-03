"""Global shortcut listener using the XDG Desktop Portal GlobalShortcuts API.

Uses org.freedesktop.portal.GlobalShortcuts via Gio.DBusConnection.
Zero pip dependencies — Gio is provided by the GNOME Platform runtime.

Supported DEs: KDE Plasma 6+, GNOME 48+, Hyprland.
Unsupported DEs get a log message with instructions for manual shortcut config.
"""

import json
import logging
import os
from pathlib import Path
import time

from gi.repository import Gio, GLib

from ui.domain.keyboard import KeyboardShortcut

logger = logging.getLogger("TFCBM.ShortcutListener")
logging.basicConfig(level=logging.INFO)

SETTINGS_FILE = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "tfcbm" / "settings.json"

PORTAL_BUS_NAME = "org.freedesktop.portal.Desktop"
PORTAL_OBJECT_PATH = "/org/freedesktop/portal/desktop"
PORTAL_SHORTCUTS_IFACE = "org.freedesktop.portal.GlobalShortcuts"
PORTAL_REQUEST_IFACE = "org.freedesktop.portal.Request"

CLIPBOARD_SERVICE_BUS_NAME = "io.github.dyslechtchitect.tfcbm.ClipboardService"
CLIPBOARD_SERVICE_OBJECT_PATH = "/io/github/dyslechtchitect/tfcbm/ClipboardService"
CLIPBOARD_SERVICE_IFACE = "io.github.dyslechtchitect.tfcbm.ClipboardService"

SHORTCUT_ID_PREFIX = "toggle-clipboard"


class ShortcutListener:
    def __init__(self, on_activated=None):
        self.bus = None
        self.session_path = None
        self.monitor = None
        self._activated_sub_id = 0
        self._portal_available = False
        self._session_counter = 0
        self._busy = False
        self._last_activate_time = 0
        self._on_activated_callback = on_activated
        self._active_shortcut_id = None

    def start(self):
        try:
            self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        except GLib.Error as e:
            logger.error("Could not connect to session bus: %s", e.message)
            return

        self._portal_available = self._check_portal_available()
        if not self._portal_available:
            logger.warning(
                "XDG GlobalShortcuts portal is not available on this desktop environment. "
                "To use a global shortcut, configure one manually in your DE's keyboard settings "
                "that runs: dbus-send --session --type=method_call "
                "--dest=io.github.dyslechtchitect.tfcbm.ClipboardService "
                "/io/github/dyslechtchitect/tfcbm/ClipboardService "
                "io.github.dyslechtchitect.tfcbm.ClipboardService.Activate uint32:0"
            )
            self.monitor_settings()
            logger.info("Shortcut listener started (portal unavailable, monitoring settings only).")
            return

        self._subscribe_activated_signal()
        self._create_session()
        self.monitor_settings()
        logger.info("Shortcut listener started.")

    def disable(self):
        """Temporarily disable the global shortcut (e.g. during recording)."""
        if self.session_path:
            logger.info("Disabling global shortcut (destroying portal session)")
            self._destroy_session()

    def enable(self):
        """Re-enable the global shortcut after recording."""
        if self._portal_available and not self.session_path:
            logger.info("Re-enabling global shortcut (creating portal session)")
            self._create_session()

    def stop(self):
        self._destroy_session()
        if self.monitor:
            self.monitor.cancel()
            self.monitor = None
        if self._activated_sub_id and self.bus:
            self.bus.signal_unsubscribe(self._activated_sub_id)
            self._activated_sub_id = 0
        logger.info("Shortcut listener stopped.")

    def _check_portal_available(self):
        """Check that the GlobalShortcuts interface is actually exposed by the portal."""
        try:
            result = self.bus.call_sync(
                PORTAL_BUS_NAME,
                PORTAL_OBJECT_PATH,
                "org.freedesktop.DBus.Introspectable",
                "Introspect",
                None,
                GLib.VariantType("(s)"),
                Gio.DBusCallFlags.NONE,
                5000,
                None,
            )
            xml = result.unpack()[0]
            return "org.freedesktop.portal.GlobalShortcuts" in xml
        except GLib.Error:
            return False

    def _sender_token(self):
        """Return a unique sender token derived from the bus connection name."""
        name = self.bus.get_unique_name()  # e.g. ":1.42"
        return name.replace(":", "").replace(".", "_")

    def _request_path(self, token):
        return f"/org/freedesktop/portal/desktop/request/{self._sender_token()}/{token}"

    def _create_session(self):
        self._busy = True
        try:
            self._create_session_inner()
        finally:
            self._busy = False

    def _create_session_inner(self):
        self._session_counter += 1
        token = f"tfcbm_session_{self._session_counter}"
        request_token = f"tfcbm_create_{self._session_counter}"

        options = {
            "handle_token": GLib.Variant("s", request_token),
            "session_handle_token": GLib.Variant("s", token),
        }

        request_path = self._request_path(request_token)

        response_received = [False]

        def on_create_response(_connection, _sender, _path, _iface, _signal, params):
            response_received[0] = True
            response_code, results = params.unpack()
            if response_code != 0:
                logger.error("CreateSession failed with response code %d", response_code)
                return
            self.session_path = results.get("session_handle", None)
            if not self.session_path:
                logger.error("CreateSession returned no session_handle")
                return
            logger.info("Portal session created: %s", self.session_path)
            self._bind_shortcuts()

        sub_id = self.bus.signal_subscribe(
            PORTAL_BUS_NAME,
            PORTAL_REQUEST_IFACE,
            "Response",
            request_path,
            None,
            Gio.DBusSignalFlags.NO_MATCH_RULE,
            on_create_response,
        )

        try:
            self.bus.call_sync(
                PORTAL_BUS_NAME,
                PORTAL_OBJECT_PATH,
                PORTAL_SHORTCUTS_IFACE,
                "CreateSession",
                GLib.Variant("(a{sv})", (options,)),
                GLib.VariantType("(o)"),
                Gio.DBusCallFlags.NONE,
                5000,
                None,
            )
        except GLib.Error as e:
            logger.error("CreateSession call failed: %s", e.message)
            self.bus.signal_unsubscribe(sub_id)
            return

        # Let the main loop process the response signal
        context = GLib.MainContext.default()
        deadline = GLib.get_monotonic_time() + 5_000_000  # 5 seconds
        while not response_received[0] and GLib.get_monotonic_time() < deadline:
            context.iteration(False)

        self.bus.signal_unsubscribe(sub_id)

        if not response_received[0]:
            logger.error("Timed out waiting for CreateSession response")

    def _bind_shortcuts(self):
        if not self.session_path:
            logger.error("No session to bind shortcuts to")
            return

        shortcut = self._load_shortcut()
        if not shortcut:
            logger.warning("No shortcut configured, skipping bind.")
            return

        xdg_str = shortcut.to_xdg_string()
        # Use a shortcut ID derived from the actual key combo so the portal
        # treats each different shortcut as a brand-new binding instead of
        # silently reusing a cached (stale) trigger for the same ID.
        shortcut_id = f"{SHORTCUT_ID_PREFIX}-{xdg_str.lower().replace('+', '-')}"
        self._active_shortcut_id = shortcut_id
        logger.info("Binding shortcut: %s (XDG: %s, ID: %s)",
                     shortcut.to_display_string(), xdg_str, shortcut_id)

        request_token = f"tfcbm_bind_{self._session_counter}"
        request_path = self._request_path(request_token)

        # Build shortcuts list and options as plain Python structures.
        # Dict values for a{sv} must be GLib.Variant objects — never use
        # .unpack() on an a{sv} variant as that strips the Variant wrappers.
        shortcuts = [
            (
                shortcut_id,
                {
                    "description": GLib.Variant("s", "Toggle TFCBM clipboard window"),
                    "preferred_trigger": GLib.Variant("s", xdg_str),
                },
            )
        ]

        options = {
            "handle_token": GLib.Variant("s", request_token),
        }

        response_received = [False]

        def on_bind_response(_connection, _sender, _path, _iface, _signal, params):
            response_received[0] = True
            response_code, results = params.unpack()
            if response_code != 0:
                logger.error("BindShortcuts failed with response code %d", response_code)
                return
            shortcuts_result = results.get("shortcuts", [])
            logger.info("Shortcuts bound successfully: %s", shortcuts_result)

        sub_id = self.bus.signal_subscribe(
            PORTAL_BUS_NAME,
            PORTAL_REQUEST_IFACE,
            "Response",
            request_path,
            None,
            Gio.DBusSignalFlags.NO_MATCH_RULE,
            on_bind_response,
        )

        try:
            self.bus.call_sync(
                PORTAL_BUS_NAME,
                PORTAL_OBJECT_PATH,
                PORTAL_SHORTCUTS_IFACE,
                "BindShortcuts",
                GLib.Variant("(oa(sa{sv})sa{sv})", (
                    self.session_path,
                    shortcuts,
                    "",  # parent_window
                    options,
                )),
                GLib.VariantType("(o)"),
                Gio.DBusCallFlags.NONE,
                5000,
                None,
            )
        except GLib.Error as e:
            logger.error("BindShortcuts call failed: %s", e.message)
            self.bus.signal_unsubscribe(sub_id)
            return

        context = GLib.MainContext.default()
        deadline = GLib.get_monotonic_time() + 5_000_000
        while not response_received[0] and GLib.get_monotonic_time() < deadline:
            context.iteration(False)

        self.bus.signal_unsubscribe(sub_id)

        if not response_received[0]:
            logger.error("Timed out waiting for BindShortcuts response")

    def _subscribe_activated_signal(self):
        self._activated_sub_id = self.bus.signal_subscribe(
            PORTAL_BUS_NAME,
            PORTAL_SHORTCUTS_IFACE,
            "Activated",
            PORTAL_OBJECT_PATH,
            None,
            Gio.DBusSignalFlags.NONE,
            self._on_portal_activated,
        )

    def _on_portal_activated(self, _connection, _sender, _path, _iface, _signal, params):
        _session_handle, shortcut_id, _timestamp, options = params.unpack()
        if shortcut_id != self._active_shortcut_id:
            return

        now = time.monotonic()
        if now - self._last_activate_time < 0.5:
            logger.debug("Ignoring duplicate portal activation (debounce)")
            return
        self._last_activate_time = now

        # Extract activation token from portal options (needed for Wayland focus)
        activation_token = ''
        if isinstance(options, dict):
            logger.debug("Portal Activated options: %s", options)
            token = options.get('activation_token', '')
            activation_token = str(token) if token else ''

        logger.info("Shortcut activated via portal! (token=%s, timestamp=%s)",
                     activation_token[:16] + '...' if len(activation_token) > 16 else activation_token,
                     _timestamp)

        if self._on_activated_callback:
            self._on_activated_callback(activation_token, _timestamp)
        else:
            self._call_activate()

    def _call_activate(self):
        def on_call_done(bus, result):
            try:
                bus.call_finish(result)
                logger.info("Called Activate method on DBus service.")
            except GLib.Error as e:
                logger.warning("Failed to call Activate: %s", e.message)

        self.bus.call(
            CLIPBOARD_SERVICE_BUS_NAME,
            CLIPBOARD_SERVICE_OBJECT_PATH,
            CLIPBOARD_SERVICE_IFACE,
            "Activate",
            GLib.Variant("(u)", (int(time.time()),)),
            None,
            Gio.DBusCallFlags.NONE,
            2000,
            None,
            on_call_done,
        )

    def _destroy_session(self):
        if self.session_path and self.bus:
            try:
                self.bus.call_sync(
                    PORTAL_BUS_NAME,
                    self.session_path,
                    "org.freedesktop.portal.Session",
                    "Close",
                    None,
                    None,
                    Gio.DBusCallFlags.NONE,
                    2000,
                    None,
                )
                logger.info("Portal session closed: %s", self.session_path)
            except GLib.Error as e:
                logger.debug("Session close failed (may already be gone): %s", e.message)
            self.session_path = None

    def _load_shortcut(self):
        try:
            if SETTINGS_FILE.exists():
                with open(SETTINGS_FILE, "r") as f:
                    config = json.load(f)
                shortcut_str = config.get("keyboard_shortcut")
                if shortcut_str:
                    return KeyboardShortcut.from_gtk_string(shortcut_str)
        except (IOError, json.JSONDecodeError) as e:
            logger.error("Error reading settings file: %s", e)
        return None

    def _reload_shortcut(self):
        if not self._portal_available:
            logger.info("Portal not available, shortcut reload skipped.")
            return
        if self._busy:
            logger.debug("Session operation in progress, skipping reload.")
            return
        logger.info("Reloading shortcut — destroying old session and creating new one.")
        self._destroy_session()
        self._create_session()

    def monitor_settings(self):
        if not SETTINGS_FILE.exists():
            logger.warning("Settings file not found, cannot monitor for changes.")
            return

        file_to_monitor = Gio.File.new_for_path(str(SETTINGS_FILE))
        self.monitor = file_to_monitor.monitor(Gio.FileMonitorFlags.NONE, None)
        self.monitor.connect("changed", self._on_settings_changed)

    def _on_settings_changed(self, _monitor, _file, _other_file, event_type):
        if event_type == Gio.FileMonitorEvent.CHANGES_DONE_HINT:
            logger.info("Settings file changed, reloading shortcut.")
            self._reload_shortcut()


if __name__ == "__main__":
    listener = ShortcutListener()
    listener.start()

    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        logger.info("Shutting down listener...")
        listener.stop()
        loop.quit()
