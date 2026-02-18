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
    def __init__(self, on_activated=None, on_shortcut_unavailable=None):
        self.bus = None
        self.session_path = None
        self.monitor = None
        self._activated_sub_id = 0
        self._portal_available = False
        self._session_counter = 0
        self._busy = False
        self._last_activate_time = 0
        self._on_activated_callback = on_activated
        self._on_shortcut_unavailable = on_shortcut_unavailable
        self._active_shortcut_id = None
        self._bind_response_sub_id = 0

    def start(self):
        try:
            self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        except GLib.Error as e:
            logger.error("Could not connect to session bus: %s", e.message)
            return

        self._portal_available = self._check_portal_available()
        if not self._portal_available:
            self._warn_no_portal()
            if self._on_shortcut_unavailable:
                GLib.idle_add(self._on_shortcut_unavailable, "unsupported_de", None)
            self.monitor_settings()
            logger.info("Shortcut listener started (portal unavailable, monitoring settings only).")
            return

        self._subscribe_activated_signal()
        self._create_session()

        if not self.session_path:
            # Session creation failed (e.g. snap confinement blocks /proc access).
            self._portal_available = False
            if self._activated_sub_id:
                self.bus.signal_unsubscribe(self._activated_sub_id)
                self._activated_sub_id = 0
            self._warn_no_portal()
            if self._on_shortcut_unavailable:
                from ui.utils.system_info import get_missing_portal_backend
                missing = get_missing_portal_backend()
                if missing:
                    GLib.idle_add(self._on_shortcut_unavailable, "missing_backend", missing)
                else:
                    GLib.idle_add(self._on_shortcut_unavailable, "unsupported_de", None)

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
        if self._bind_response_sub_id and self.bus:
            self.bus.signal_unsubscribe(self._bind_response_sub_id)
            self._bind_response_sub_id = 0
        if self._activated_sub_id and self.bus:
            self.bus.signal_unsubscribe(self._activated_sub_id)
            self._activated_sub_id = 0
        logger.info("Shortcut listener stopped.")

    def _warn_no_portal(self):
        """Log instructions for manual shortcut setup."""
        shortcut = self._load_shortcut()
        binding_str = shortcut.to_display_string() if shortcut else "Ctrl+Escape"
        gsettings_str = shortcut.to_gsettings_string() if shortcut else "<Control>Escape"

        if os.environ.get("SNAP"):
            logger.warning(
                "GlobalShortcuts portal is not usable under snap confinement. "
                "Run this command ONCE in a host terminal to set up the keyboard shortcut:\n\n"
                "  bash -c 'PATH_LIST=$(gsettings get org.gnome.settings-daemon.plugins.media-keys "
                "custom-keybindings); "
                "if echo \"$PATH_LIST\" | grep -q tfcbm; then echo \"Already registered\"; else "
                "NEW=$(echo \"$PATH_LIST\" | sed \"s|\\]|, "
                "\\x27/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/tfcbm/\\x27]|;"
                "s|\\@as \\[\\], |[|;s|\\[, |[|\"); "
                "gsettings set org.gnome.settings-daemon.plugins.media-keys custom-keybindings "
                "\"$NEW\"; "
                "gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:"
                "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/tfcbm/ "
                "name \"TFCBM Clipboard Manager\"; "
                "gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:"
                "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/tfcbm/ "
                "command \"snap run tfcbm\"; "
                "gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:"
                "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/tfcbm/ "
                "binding \"%s\"; "
                "echo \"Shortcut registered: %s → snap run tfcbm\"; fi'"
                % (gsettings_str, binding_str)
            )
        else:
            logger.warning(
                "XDG GlobalShortcuts portal is not available on this desktop environment. "
                "To use a global shortcut, configure one manually in your DE's keyboard settings "
                "that runs: snap run tfcbm"
            )

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
            if "org.freedesktop.portal.GlobalShortcuts" in xml:
                return True
            # In sandboxed environments (snap), the D-Bus proxy may filter
            # introspection XML.  Try a direct method call as fallback.
            logger.info("GlobalShortcuts not in introspection XML, probing directly...")
        except GLib.Error:
            return False

        # Direct probe: attempt to read the interface version property.
        # An UnknownInterface / UnknownMethod error means it truly doesn't exist.
        try:
            self.bus.call_sync(
                PORTAL_BUS_NAME,
                PORTAL_OBJECT_PATH,
                "org.freedesktop.DBus.Properties",
                "Get",
                GLib.Variant("(ss)", (PORTAL_SHORTCUTS_IFACE, "version")),
                GLib.VariantType("(v)"),
                Gio.DBusCallFlags.NONE,
                5000,
                None,
            )
            logger.info("GlobalShortcuts portal confirmed via direct probe")
            return True
        except GLib.Error as e:
            msg = str(e.message) if e.message else ""
            if "UnknownInterface" in msg or "UnknownMethod" in msg or "No such interface" in msg:
                return False
            # Other errors (e.g. access denied) suggest the interface exists
            logger.info("GlobalShortcuts probe returned '%s', assuming available", msg)
            return True

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
        elif self.session_path:
            self._bind_shortcuts()

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
        logger.info("Checking shortcut: %s (XDG: %s, ID: %s)",
                     shortcut.to_display_string(), xdg_str, shortcut_id)

        # Check if the shortcut is already bound via ListShortcuts.
        # If it is, skip BindShortcuts to avoid showing the system dialog.
        if self._is_shortcut_already_bound(shortcut_id):
            logger.info("Shortcut '%s' is already bound, skipping BindShortcuts dialog.",
                         shortcut.to_display_string())
            return

        logger.info("Shortcut not yet bound, calling BindShortcuts (may show system dialog).")
        self._do_bind_shortcuts(shortcut_id, xdg_str)

    def _is_shortcut_already_bound(self, shortcut_id):
        """Check if the shortcut is already bound in the current portal session."""
        request_token = f"tfcbm_list_{self._session_counter}"
        request_path = self._request_path(request_token)

        options = {
            "handle_token": GLib.Variant("s", request_token),
        }

        response_received = [False]
        already_bound = [False]

        def on_list_response(_connection, _sender, _path, _iface, _signal, params):
            response_received[0] = True
            response_code, results = params.unpack()
            if response_code != 0:
                logger.debug("ListShortcuts returned response code %d", response_code)
                return
            shortcuts_list = results.get("shortcuts", [])
            logger.debug("ListShortcuts returned: %s", shortcuts_list)
            for sc in shortcuts_list:
                if isinstance(sc, tuple) and len(sc) >= 1 and sc[0] == shortcut_id:
                    already_bound[0] = True
                    break

        sub_id = self.bus.signal_subscribe(
            PORTAL_BUS_NAME,
            PORTAL_REQUEST_IFACE,
            "Response",
            request_path,
            None,
            Gio.DBusSignalFlags.NO_MATCH_RULE,
            on_list_response,
        )

        try:
            self.bus.call_sync(
                PORTAL_BUS_NAME,
                PORTAL_OBJECT_PATH,
                PORTAL_SHORTCUTS_IFACE,
                "ListShortcuts",
                GLib.Variant("(oa{sv})", (
                    self.session_path,
                    options,
                )),
                GLib.VariantType("(o)"),
                Gio.DBusCallFlags.NONE,
                5000,
                None,
            )
        except GLib.Error as e:
            logger.debug("ListShortcuts call failed: %s", e.message)
            self.bus.signal_unsubscribe(sub_id)
            return False

        context = GLib.MainContext.default()
        deadline = GLib.get_monotonic_time() + 5_000_000
        while not response_received[0] and GLib.get_monotonic_time() < deadline:
            context.iteration(False)

        self.bus.signal_unsubscribe(sub_id)

        if not response_received[0]:
            logger.debug("Timed out waiting for ListShortcuts response")
            return False

        return already_bound[0]

    def _do_bind_shortcuts(self, shortcut_id, xdg_str):
        """Call BindShortcuts on the portal, which may show a system dialog.

        This is intentionally asynchronous — the portal may present a dialog
        that requires user interaction, so we must not block the main loop
        waiting for the response.
        """
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

        def on_bind_response(_connection, _sender, _path, _iface, _signal, params):
            self.bus.signal_unsubscribe(self._bind_response_sub_id)
            self._bind_response_sub_id = 0
            response_code, results = params.unpack()
            if response_code != 0:
                logger.error("BindShortcuts failed with response code %d", response_code)
                if self._on_shortcut_unavailable:
                    from ui.utils.system_info import get_missing_portal_backend
                    missing = get_missing_portal_backend()
                    if missing:
                        GLib.idle_add(self._on_shortcut_unavailable, "missing_backend", missing)
                    else:
                        GLib.idle_add(self._on_shortcut_unavailable, "bind_error", None)
                return
            shortcuts_result = results.get("shortcuts", [])
            logger.info("Shortcuts bound successfully: %s", shortcuts_result)

        self._bind_response_sub_id = self.bus.signal_subscribe(
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
            self.bus.signal_unsubscribe(self._bind_response_sub_id)
            self._bind_response_sub_id = 0
            return

        logger.info("BindShortcuts request sent, waiting for portal response (may show dialog).")

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
        # Fall back to default Ctrl+Escape so the shortcut gets bound on
        # first launch even before the user opens the settings page.
        logger.info("No shortcut in settings, using default: Ctrl+Escape")
        return KeyboardShortcut(modifiers=["Ctrl"], key="Escape")

    def _reload_shortcut(self):
        if not self._portal_available:
            logger.info("Portal not available, cannot reload shortcut via portal.")
            if self._on_shortcut_unavailable:
                GLib.idle_add(self._on_shortcut_unavailable, "unsupported_de", None)
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
