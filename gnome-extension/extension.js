/*
 * TFCBM GNOME Shell Extension
 *
 * Lifecycle Integration:
 * - Extension monitors clipboard and provides tray icon when enabled
 * - Tray icon is ONLY visible when the TFCBM app is running (not just when extension is enabled)
 * - App automatically enables extension on launch (see ui/application/clipboard_app.py)
 * - App automatically disables extension on quit (see server/src/dbus_service.py)
 * - "Start on Login" setting in app controls whether app launches at login (extension follows app lifecycle)
 *
 * This creates an integrated experience where users control TFCBM as one system,
 * and the tray icon clearly indicates when the app is active.
 */

import { Extension } from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import St from 'gi://St';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import GObject from 'gi://GObject';
import Clutter from 'gi://Clutter';
import Shell from 'gi://Shell';
import { ClipboardMonitorService } from './src/ClipboardMonitorService.js';
import { GnomeClipboardAdapter } from './src/adapters/GnomeClipboardAdapter.js';
import { DBusNotifier } from './src/adapters/DBusNotifier.js';
import { PollingScheduler } from './src/PollingScheduler.js';

const DBUS_NAME = 'io.github.dyslechtchitect.tfcbm';
const DBUS_PATH = '/org/tfcbm/ClipboardService';
const DBUS_IFACE = 'org.tfcbm.ClipboardService';

// D-Bus constants for the extension's OWN service (to be consumed by the Flatpak app)
const EXTENSION_DBUS_NAME = 'org.gnome.Shell.Extensions.TfcbmClipboardMonitor';
const EXTENSION_DBUS_PATH = '/org/gnome/Shell/Extensions/TfcbmClipboardMonitor';
const EXTENSION_DBUS_IFACE_XML = `
<node>
    <interface name="${EXTENSION_DBUS_NAME}">
        <method name="GetSetting">
            <arg type="s" name="schema_id" direction="in"/>
            <arg type="s" name="key" direction="in"/>
            <arg type="s" name="value" direction="out"/>
        </method>
        <method name="SetSetting">
            <arg type="s" name="schema_id" direction="in"/>
            <arg type="s" name="key" direction="in"/>
            <arg type="s" name="value" direction="in"/>
        </method>
        <!-- Methods for global input monitoring/paste simulation could be added here -->
        <method name="SimulatePaste"/>
    </interface>
</node>
`;

const DBusInterface = `
<node>
    <interface name="org.tfcbm.ClipboardService">
        <method name="Activate">
            <arg type="u" name="timestamp" direction="in"/>
        </method>
        <method name="ShowSettings">
            <arg type="u" name="timestamp" direction="in"/>
        </method>
        <method name="Quit"/>
        <method name="GetSetting">
            <arg type="s" name="schema_id" direction="in"/>
            <arg type="s" name="key" direction="in"/>
            <arg type="s" name="value" direction="out"/>
        </method>
        <method name="SetSetting">
            <arg type="s" name="schema_id" direction="in"/>
            <arg type="s" name="key" direction="in"/>
            <arg type="s" name="value" direction="in"/>
        </method>
    </interface>
</node>
`;

// Custom PanelMenu.Button that intercepts left-click to toggle UI instead of showing menu
const TFCBMIndicator = GObject.registerClass(
class TFCBMIndicator extends PanelMenu.Button {
    _init(extension) {
        super._init(0.0, 'TFCBM Clipboard Monitor', false);
        this._extension = extension;
    }

    vfunc_event(event) {
        // Intercept left-click to toggle UI instead of opening menu
        if (event.type() === Clutter.EventType.BUTTON_PRESS) {
            const button = event.get_button();
            if (button === 1) { // Left click
                this._extension._toggleUI();
                return Clutter.EVENT_STOP; // Stop event propagation (don't open menu)
            }
        }
        // For all other events (including right-click), use default behavior (show menu)
        return super.vfunc_event(event);
    }
});

export default class ClipboardMonitorExtension extends Extension {
    constructor(metadata) {
        super(metadata);
        this._indicator = null;
        this._scheduler = null;
        this._settings = null;
        this._settingsChangedId = null;
        this._dbus = null;
        this._dbusOwner = null;
        this._dbusOwnerWatchId = null;
        this._icon = null;
        this._exportedDBusId = null; // Registration ID for our exported D-Bus object
        this._busNameOwnerId = null; // Bus name ownership ID
    }

    _launchApp() {
        try {
            let command;
            // Check if running inside a Flatpak sandbox
            if (GLib.file_test('/.flatpak-info', GLib.FileTest.EXISTS)) {
                command = ['flatpak', 'run', 'io.github.dyslechtchitect.tfcbm', '--activate'];
            } else {
                command = ['tfcbm', '--activate'];
            }
            
            GLib.spawn_async(
                null, // CWD
                command,
                null, // envp
                GLib.SpawnFlags.SEARCH_PATH | GLib.SpawnFlags.DO_NOT_REAP_CHILD,
                null // child_setup
            );
        } catch (e) {
            logError(e, 'Failed to launch TFCBM');
        }
    }

    _toggleUI() {
        if (this._dbusOwner) {
            try {
                const timestamp = global.display.get_current_time_roundtrip();
                this._dbus.ActivateRemote(timestamp);
            } catch (e) {
                logError(e, 'Failed to activate TFCBM UI');
                this._launchApp();
            }
        } else {
            this._launchApp();
        }
    }

    _onOwnerChanged(connection, name, owner) {
        this._dbusOwner = owner;
        this._updateIconStyle();
    }

    _updateIconStyle() {
        if (!this._icon || !this._indicator) return;

        if (this._dbusOwner) {
            // App is running - show tray icon with normal style
            this._indicator.visible = true;
            this._icon.remove_style_class_name('disabled');
        } else {
            // App is not running - hide tray icon completely
            // This makes it clear that the system is not active
            this._indicator.visible = false;
        }
    }

    _reconnect() {
        if (this._dbus) {
            this._dbus.g_connection.signal_unsubscribe(this._dbusOwnerWatchId);
            this._dbus = null;
        }

        this._dbusOwnerWatchId = Gio.DBus.session.signal_subscribe(
            'org.freedesktop.DBus', // sender
            'org.freedesktop.DBus', // iface
            'NameOwnerChanged', // member
            '/org/freedesktop/DBus', // path
            DBUS_NAME, // arg0
            Gio.DBusSignalFlags.NONE,
            this._onOwnerChanged.bind(this)
        );

        // Parse the D-Bus interface XML
        const nodeInfo = Gio.DBusNodeInfo.new_for_xml(DBusInterface);
        const interfaceInfo = nodeInfo.lookup_interface(DBUS_IFACE);

        // Use DO_NOT_AUTO_START to prevent triggering D-Bus auto-activation
        // This ensures the extension doesn't force-launch TFCBM on login
        // D-Bus communication still works when app is manually started or via XDG autostart
        Gio.DBusProxy.new_for_bus(
            Gio.BusType.SESSION,
            Gio.DBusProxyFlags.DO_NOT_AUTO_START,
            interfaceInfo, // interface info
            DBUS_NAME,
            DBUS_PATH,
            DBUS_IFACE,
            null, // cancellable
            (source, result) => {
                try {
                    this._dbus = Gio.DBusProxy.new_for_bus_finish(result);
                    this._dbusOwner = this._dbus.g_name_owner;
                } catch (e) {
                    this._dbus = null;
                    this._dbusOwner = null;
                }
                this._updateIconStyle();
            }
        );
    }

    _showSettings() {
        if (!this._dbus) return;
        try {
            const timestamp = global.display.get_current_time_roundtrip();
            this._dbus.ShowSettingsRemote(timestamp);
        } catch (e) {
            logError(e, 'Failed to show TFCBM settings');
        }
    }

    _quitApp() {
        if (!this._dbus) return;
        try {
            this._dbus.QuitRemote();
        } catch (e) {
            logError(e, 'Failed to quit TFCBM');
        }
    }

    // D-Bus methods for Flatpak to read/write extension settings
    _GetSetting(schema_id, key) {
        if (!this._settings) {
            throw new Gio.DBusError(Gio.DBusError.quark(), Gio.DBusError.Code.FAILED, `Extension settings not initialized.`);
        }
        // Ensure the schema_id matches the extension's schema
        if (schema_id !== this._settings.schema_id) {
            logError(new Error(`TFCBM Extension: Requested schema_id '${schema_id}' does not match extension schema '${this._settings.schema_id}'`), 'Invalid schema_id for GetSetting');
            throw new Gio.DBusError(Gio.DBusError.quark(), Gio.DBusError.Code.INVALID_ARGS, `Invalid schema_id: ${schema_id}`);
        }

        try {
            // Get the GSettings value as a string (assuming all settings for Flatpak are strings)
            const value = this._settings.get_string(key);
            log(`TFCBM Extension: GetSetting('${key}') -> '${value}'`);
            return value;
        } catch (e) {
            logError(e, `TFCBM Extension: Failed to get setting for key '${key}'`);
            throw new Gio.DBusError(Gio.DBusError.quark(), Gio.DBusError.Code.FAILED, `Failed to get setting '${key}': ${e.message}`);
        }
    }

    _SetSetting(schema_id, key, value) {
        if (!this._settings) {
            throw new Gio.DBusError(Gio.DBusError.quark(), Gio.DBusError.Code.FAILED, `Extension settings not initialized.`);
        }
        // Ensure the schema_id matches the extension's schema
        if (schema_id !== this._settings.schema_id) {
            logError(new Error(`TFCBM Extension: Requested schema_id '${schema_id}' does not match extension schema '${this._settings.schema_id}'`), 'Invalid schema_id for SetSetting');
            throw new Gio.DBusError(Gio.DBusError.quark(), Gio.DBusError.Code.INVALID_ARGS, `Invalid schema_id: ${schema_id}`);
        }

        try {
            // Set the GSettings value as a string
            this._settings.set_string(key, value);
            log(`TFCBM Extension: SetSetting('${key}', '${value}') successful`);
            // Trigger re-registration if the key is 'toggle-tfcbm-ui' (for the shortcut)
            if (key === 'toggle-tfcbm-ui') {
                this._reregisterKeybinding();
            }
        } catch (e) {
            logError(e, `TFCBM Extension: Failed to set setting for key '${key}' to '${value}'`);
            throw new Gio.DBusError(Gio.DBusError.quark(), Gio.DBusError.Code.FAILED, `Failed to set setting '${key}': ${e.message}`);
        }
    }

    // D-Bus method for Flatpak to request paste simulation on the host
    _SimulatePaste() {
        log('[TFCBM Extension] Received request to simulate paste.');
        let cmd = [];
        let success = false;

        // Try xdotool first (X11)
        try {
            cmd = ['xdotool', 'key', 'ctrl+v'];
            const [res, pid, stdin, stdout, stderr] = GLib.spawn_sync(
                null, // CWD
                cmd,
                null, // envp
                GLib.SpawnFlags.SEARCH_PATH | GLib.SpawnFlags.DO_NOT_REAP_CHILD,
                null // child_setup
            );
            if (res) {
                const status = GLib.get_child_status(GLib.Pid.from_string(pid), stdout, stderr, null);
                if (status === 0) {
                    log('[TFCBM Extension] Simulated Ctrl+V paste with xdotool');
                    success = true;
                } else {
                    logError(new Error(`xdotool failed with status ${status}: ${stderr.toString()}`), '[TFCBM Extension] xdotool error');
                }
            }
        } catch (e) {
            logError(e, '[TFCBM Extension] xdotool not available or error');
        }

        if (!success) {
            // Try ydotool (Wayland) if xdotool failed
            try {
                cmd = [
                    'ydotool', 'key',
                    '29:1', '47:1', '47:0', '29:0' // Ctrl+V
                ];
                const [res, pid, stdin, stdout, stderr] = GLib.spawn_sync(
                    null, // CWD
                    cmd,
                    null, // envp
                    GLib.SpawnFlags.SEARCH_PATH | GLib.SpawnFlags.DO_NOT_REAP_CHILD,
                    null // child_setup
                );
                if (res) {
                    const status = GLib.get_child_status(GLib.Pid.from_string(pid), stdout, stderr, null);
                    if (status === 0) {
                        log('[TFCBM Extension] Simulated Ctrl+V paste with ydotool');
                        success = true;
                    } else {
                        logError(new Error(`ydotool failed with status ${status}: ${stderr.toString()}`), '[TFCBM Extension] ydotool error');
                    }
                }
            } catch (e) {
                logError(e, '[TFCBM Extension] ydotool not available or error');
            }
        }

        if (!success) {
            log('[TFCBM Extension] Failed to simulate paste: neither xdotool nor ydotool worked.');
            throw new Gio.DBusError(Gio.DBusError.quark(), Gio.DBusError.Code.FAILED, 'Failed to simulate paste: neither xdotool nor ydotool worked.');
        }
    }



    _registerKeybinding() {
        try {
            const currentBinding = this._settings.get_strv('toggle-tfcbm-ui');
            log(`[TFCBM] Registering keyboard shortcut: ${currentBinding}`);

            Main.wm.addKeybinding(
                'toggle-tfcbm-ui',
                this._settings,
                0, // Gio.SettingsBindFlags.DEFAULT
                Shell.ActionMode.NORMAL | Shell.ActionMode.OVERVIEW, // Allow in normal mode and overview
                () => {
                    log('[TFCBM] Keyboard shortcut activated');
                    this._toggleUI();
                }
            );
            log('[TFCBM] Keyboard shortcut registered successfully');
        } catch (e) {
            logError(e, '[TFCBM] Failed to register keyboard shortcut');
        }
    }

    _reregisterKeybinding() {
        try {
            // Remove old keybinding
            Main.wm.removeKeybinding('toggle-tfcbm-ui');

            // Re-register with new shortcut
            this._registerKeybinding();

            log('[TFCBM] Keyboard shortcut successfully updated');
        } catch (e) {
            logError(e, 'TFCBM: Error re-registering keybinding');
        }
    }

    enable() {
        log('[TFCBM] Extension enable() called - starting initialization...');

        // Initialize clipboard monitoring
        const clipboardAdapter = new GnomeClipboardAdapter();
        const notifier = new DBusNotifier();
        const service = new ClipboardMonitorService(clipboardAdapter, notifier);

        this._scheduler = new PollingScheduler(() => {
            service.checkAndNotify();
        }, 250);

        this._scheduler.start();
        log('[TFCBM] Clipboard monitoring started (250ms polling)');

        // Add keyboard shortcut
        try {
            log('[TFCBM] Getting extension settings...');
            this._settings = this.getSettings();

            if (!this._settings) {
                throw new Error('getSettings() returned null');
            }

            log('[TFCBM] Settings obtained successfully');
            this._registerKeybinding();

            // Listen for changes to the shortcut setting
            this._settingsChangedId = this._settings.connect('changed::toggle-tfcbm-ui', () => {
                log('[TFCBM] Keyboard shortcut changed, re-registering...');
                this._reregisterKeybinding();
            });
        } catch (e) {
            logError(e, 'TFCBM: Error adding keybinding');
        }

        // Create system tray indicator
        try {
            this._indicator = new TFCBMIndicator(this);

            // Load custom icon from extension directory
            const iconPath = `${this.metadata.path}/tfcbm.svg`;

            if (GLib.file_test(iconPath, GLib.FileTest.EXISTS)) {
                const gicon = Gio.icon_new_for_string(iconPath);
                this._icon = new St.Icon({
                    gicon: gicon,
                    style_class: 'system-status-icon',
                });
            } else {
                // Fallback to system icon
                this._icon = new St.Icon({
                    icon_name: 'edit-paste-symbolic',
                    style_class: 'system-status-icon',
                });
            }

            this._indicator.add_child(this._icon);

            // Create popup menu (right-click)
            const settingsItem = new PopupMenu.PopupMenuItem('TFCBM Settings');
            settingsItem.connect('activate', () => {
                this._showSettings();
            });
            this._indicator.menu.addMenuItem(settingsItem);

            // Add separator
            this._indicator.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

            const quitAppItem = new PopupMenu.PopupMenuItem('Quit TFCBM App');
            quitAppItem.connect('activate', () => {
                this._quitApp();
            });
            this._indicator.menu.addMenuItem(quitAppItem);

            // Add to panel
            Main.panel.addToStatusArea('tfcbm-indicator', this._indicator);

            this._updateIconStyle();
        } catch (e) {
            logError(e, 'TFCBM: Error creating tray indicator');
        }

        // Export D-Bus interface for the Flatpak app to use
        try {
            log('[TFCBM] Attempting to export D-Bus service...');
            const nodeInfo = Gio.DBusNodeInfo.new_for_xml(EXTENSION_DBUS_IFACE_XML);
            log('[TFCBM] XML parsed successfully');
            const interfaceInfo = nodeInfo.lookup_interface(EXTENSION_DBUS_NAME);
            log(`[TFCBM] Interface info obtained for ${EXTENSION_DBUS_NAME}`);

            // Register D-Bus object using the modern API
            this._exportedDBusId = Gio.DBus.session.register_object(
                EXTENSION_DBUS_PATH,
                interfaceInfo,
                (connection, sender, objectPath, interfaceName, methodName, parameters, invocation) => {
                    try {
                        log(`[TFCBM Extension] D-Bus method called: ${methodName}`);
                        let result;
                        if (methodName === 'GetSetting') {
                            const [schema_id, key] = parameters.deepUnpack();
                            result = this._GetSetting(schema_id, key);
                            invocation.return_value(GLib.Variant.new('(s)', [result]));
                        } else if (methodName === 'SetSetting') {
                            const [schema_id, key, value] = parameters.deepUnpack();
                            this._SetSetting(schema_id, key, value);
                            invocation.return_value(null);
                        } else if (methodName === 'SimulatePaste') {
                            this._SimulatePaste();
                            invocation.return_value(null);
                        } else {
                            invocation.return_error_literal(Gio.DBusError.quark(), Gio.DBusError.Code.UNKNOWN_METHOD, 'Unknown method');
                        }
                    } catch (e) {
                        logError(e, `TFCBM Extension: Error handling D-Bus method call ${methodName}`);
                        invocation.return_error_literal(Gio.DBusError.quark(), Gio.DBusError.Code.FAILED, e.message);
                    }
                },
                null, // get property handler
                null  // set property handler
            );
            log(`[TFCBM] Extension D-Bus service '${EXTENSION_DBUS_NAME}' exported on path '${EXTENSION_DBUS_PATH}' with ID ${this._exportedDBusId}`);

            // Own the D-Bus name so clients can find us
            this._busNameOwnerId = Gio.DBus.session.own_name(
                EXTENSION_DBUS_NAME,
                Gio.BusNameOwnerFlags.NONE,
                null, // name acquired callback
                null  // name lost callback
            );
            log(`[TFCBM] D-Bus name '${EXTENSION_DBUS_NAME}' ownership requested`);
        } catch (e) {
            logError(e, 'TFCBM: Error exporting extension D-Bus service');
        }

        this._reconnect();

        // Set initial icon visibility (will be hidden if app not running)
        this._updateIconStyle();

        log('[TFCBM] Extension enable() complete - extension is now active');
    }

    disable() {
        log('[TFCBM] Extension disable() called - shutting down...');

        // Stop clipboard monitoring
        if (this._scheduler) {
            this._scheduler.stop();
            this._scheduler = null;
        }

        // Remove keybinding and disconnect settings listener
        if (this._settings) {
            if (this._settingsChangedId) {
                this._settings.disconnect(this._settingsChangedId);
                this._settingsChangedId = null;
            }
            Main.wm.removeKeybinding('toggle-tfcbm-ui');
            this._settings = null;
        }

        // Remove tray indicator
        if (this._indicator) {
            this._indicator.destroy();
            this._indicator = null;
            this._icon = null;
        }

        // Disconnect DBus owner watch
        if (this._dbusOwnerWatchId) {
            Gio.DBus.session.signal_unsubscribe(this._dbusOwnerWatchId);
            this._dbusOwnerWatchId = null;
        }
        // Unexport extension D-Bus service
        if (this._exportedDBusId) {
            Gio.DBus.session.unregister_object(this._exportedDBusId);
            this._exportedDBusId = null;
            log(`[TFCBM] Extension D-Bus service '${EXTENSION_DBUS_NAME}' unexported.`);
        }

        // Unown the D-Bus name
        if (this._busNameOwnerId) {
            Gio.DBus.session.unown_name(this._busNameOwnerId);
            this._busNameOwnerId = null;
            log(`[TFCBM] D-Bus name '${EXTENSION_DBUS_NAME}' unowned.`);
        }

        if (this._dbus) {
            this._dbus = null;
        }
    }
}
