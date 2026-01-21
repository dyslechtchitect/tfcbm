/*
 * TFCBM GNOME Shell Extension
 *
 * Provides clipboard monitoring and keyboard shortcuts for TFCBM.
 * - Monitors clipboard changes and notifies the app via DBus
 * - Registers global keyboard shortcut to toggle the UI
 * - Provides DBus interface for the Flatpak app to interact with the host
 */

import { Extension } from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Shell from 'gi://Shell';
import { ClipboardMonitorService } from './src/ClipboardMonitorService.js';
import { GnomeClipboardAdapter } from './src/adapters/GnomeClipboardAdapter.js';
import { DBusNotifier } from './src/adapters/DBusNotifier.js';
import { PollingScheduler } from './src/PollingScheduler.js';

const DBUS_NAME = 'io.github.dyslechtchitect.tfcbm.ClipboardService';
const DBUS_PATH = '/io/github/dyslechtchitect/tfcbm/ClipboardService';
const DBUS_IFACE = 'io.github.dyslechtchitect.tfcbm.ClipboardService';

// D-Bus constants for the extension's OWN service (to be consumed by the Flatpak app)
const EXTENSION_DBUS_NAME = 'io.github.dyslechtchitect.tfcbm.Extension';
const EXTENSION_DBUS_PATH = '/io/github/dyslechtchitect/tfcbm/Extension';
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
        <method name="DisableKeybinding"/>
        <method name="EnableKeybinding"/>
        <method name="StartMonitoring"/>
        <method name="StopMonitoring"/>
    </interface>
</node>
`;

const DBusInterface = `
<node>
    <interface name="io.github.dyslechtchitect.tfcbm.ClipboardService">
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

export default class ClipboardMonitorExtension extends Extension {
    constructor(metadata) {
        super(metadata);
        this._scheduler = null;
        this._clipboardService = null;
        this._settings = null;
        this._settingsChangedId = null;
        this._dbus = null;
        this._dbusOwner = null;
        this._dbusOwnerWatchId = null;
        this._exportedDBusId = null; // Registration ID for our exported D-Bus object
        this._appWatchId = null; // Watcher for app's D-Bus service
        this._busNameOwnerId = null; // Bus name ownership ID
        this._keybindingDisabled = false; // Track if keybinding is temporarily disabled
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
        // Only toggle UI if app is already running (dock icon visible)
        // Don't auto-launch - user must explicitly start the app
        if (this._dbusOwner) {
            try {
                const timestamp = global.display.get_current_time_roundtrip();
                this._dbus.ActivateRemote(timestamp);
            } catch (e) {
                logError(e, 'Failed to activate TFCBM UI');
            }
        }
        // Do nothing if app is not running - keyboard shortcut only works when app is visible
    }

    _onOwnerChanged(connection, sender, path, iface, signal, params) {
        // NameOwnerChanged signal: (name, old_owner, new_owner)
        const [name, oldOwner, newOwner] = params.deep_unpack();
        log(`[TFCBM] DBus name owner changed: ${name}, old=${oldOwner}, new=${newOwner}`);

        const wasRunning = !!this._dbusOwner;
        const isRunning = !!newOwner;

        this._dbusOwner = newOwner;

        // Only update monitoring state if the state actually changed
        if (wasRunning !== isRunning) {
            log(`[TFCBM] App running state changed: ${wasRunning} -> ${isRunning}`);
            this._updateMonitoringState();
        }
    }

    _updateMonitoringState() {
        if (this._dbusOwner) {
            // Start clipboard monitoring when app is running
            if (!this._scheduler && this._clipboardService) {
                log('[TFCBM] Starting clipboard monitoring (app is running)');
                this._scheduler = new PollingScheduler(() => {
                    this._clipboardService.checkAndNotify();
                }, 250);
                this._scheduler.start();
            }
        } else {
            // Stop clipboard monitoring when app is not running
            if (this._scheduler) {
                log('[TFCBM] Stopping clipboard monitoring (app is not running)');
                this._scheduler.stop();
                this._scheduler = null;
            }
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
                this._updateMonitoringState();
            }
        );
    }

    // D-Bus methods for Flatpak to read/write extension settings
    _GetSetting(schema_id, key) {
        if (!this._settings) {
            throw new Error(`Extension settings not initialized.`);
        }
        // Ensure the schema_id matches the extension's schema
        if (schema_id !== this._settings.schema_id) {
            logError(new Error(`TFCBM Extension: Requested schema_id '${schema_id}' does not match extension schema '${this._settings.schema_id}'`), 'Invalid schema_id for GetSetting');
            throw new Error(`Invalid schema_id: ${schema_id}`);
        }

        try {
            // For the keyboard shortcut, we need to read the array and return the first element as a string
            if (key === 'toggle-tfcbm-ui') {
                const valueArray = this._settings.get_strv(key);
                const value = valueArray.length > 0 ? valueArray[0] : '';
                log(`TFCBM Extension: GetSetting('${key}') -> '${value}' (from array: [${valueArray.join(', ')}])`);
                return value;
            }
            // For other settings, use get_string
            const value = this._settings.get_string(key);
            log(`TFCBM Extension: GetSetting('${key}') -> '${value}'`);
            return value;
        } catch (e) {
            logError(e, `TFCBM Extension: Failed to get setting for key '${key}'`);
            throw new Error(`Failed to get setting '${key}': ${e.message}`);
        }
    }

    _SetSetting(schema_id, key, value) {
        if (!this._settings) {
            throw new Error(`Extension settings not initialized.`);
        }
        // Ensure the schema_id matches the extension's schema
        if (schema_id !== this._settings.schema_id) {
            logError(new Error(`TFCBM Extension: Requested schema_id '${schema_id}' does not match extension schema '${this._settings.schema_id}'`), 'Invalid schema_id for SetSetting');
            throw new Error(`Invalid schema_id: ${schema_id}`);
        }

        try {
            // For the keyboard shortcut, we need to convert the string to an array
            if (key === 'toggle-tfcbm-ui') {
                // Convert single string like "<Control><Shift>v" to array ["<Control><Shift>v"]
                this._settings.set_strv(key, [value]);
                log(`TFCBM Extension: SetSetting('${key}', ['${value}']) successful (converted to array)`);
                // Trigger re-registration for the shortcut
                this._reregisterKeybinding();
            } else {
                // For other settings, use set_string
                this._settings.set_string(key, value);
                log(`TFCBM Extension: SetSetting('${key}', '${value}') successful`);
            }
        } catch (e) {
            logError(e, `TFCBM Extension: Failed to set setting for key '${key}' to '${value}'`);
            throw new Error(`Failed to set setting '${key}': ${e.message}`);
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
            throw new Error('Failed to simulate paste: neither xdotool nor ydotool worked.');
        }
    }

    _DisableKeybinding() {
        try {
            log('[TFCBM Extension] Disabling keybinding for recording');
            Main.wm.removeKeybinding('toggle-tfcbm-ui');
            this._keybindingDisabled = true;
            log('[TFCBM Extension] Keybinding disabled successfully');
        } catch (e) {
            logError(e, '[TFCBM Extension] Error disabling keybinding');
            throw new Error(`Failed to disable keybinding: ${e.message}`);
        }
    }

    _EnableKeybinding() {
        try {
            log('[TFCBM Extension] Re-enabling keybinding after recording');
            this._registerKeybinding();
            this._keybindingDisabled = false;
            log('[TFCBM Extension] Keybinding re-enabled successfully');
        } catch (e) {
            logError(e, '[TFCBM Extension] Error re-enabling keybinding');
            throw new Error(`Failed to re-enable keybinding: ${e.message}`);
        }
    }

    _StartMonitoring() {
        try {
            log('[TFCBM Extension] Received request to start clipboard monitoring');
            if (!this._scheduler && this._clipboardService) {
                log('[TFCBM Extension] Starting clipboard polling scheduler');
                this._scheduler = new PollingScheduler(() => {
                    this._clipboardService.checkClipboard();
                }, 500);
                this._scheduler.start();
                log('[TFCBM Extension] ✓ Clipboard monitoring started');
            } else if (this._scheduler) {
                log('[TFCBM Extension] Clipboard monitoring already running');
            } else {
                log('[TFCBM Extension] Cannot start monitoring: clipboard service not initialized');
                throw new Error('Clipboard service not initialized');
            }
        } catch (e) {
            logError(e, '[TFCBM Extension] Error starting monitoring');
            throw new Error(`Failed to start monitoring: ${e.message}`);
        }
    }

    _StopMonitoring() {
        try {
            log('[TFCBM Extension] Received request to stop clipboard monitoring');
            if (this._scheduler) {
                log('[TFCBM Extension] Stopping clipboard polling scheduler');
                this._scheduler.stop();
                this._scheduler = null;
                log('[TFCBM Extension] ✓ Clipboard monitoring stopped');
            } else {
                log('[TFCBM Extension] Clipboard monitoring already stopped');
            }
        } catch (e) {
            logError(e, '[TFCBM Extension] Error stopping monitoring');
            throw new Error(`Failed to stop monitoring: ${e.message}`);
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
            const currentBinding = this._settings.get_strv('toggle-tfcbm-ui');
            log(`[TFCBM] Re-registering keyboard shortcut: ${currentBinding}`);

            // Remove old keybinding
            Main.wm.removeKeybinding('toggle-tfcbm-ui');
            log('[TFCBM] Old keybinding removed');

            // Re-register with new shortcut
            this._registerKeybinding();

            log('[TFCBM] Keyboard shortcut successfully updated');
        } catch (e) {
            logError(e, 'TFCBM: Error re-registering keybinding');
        }
    }

    enable() {
        log('[TFCBM] Extension enable() called - starting initialization...');

        // DON'T start clipboard monitoring yet - it will start when app launches
        // Store the clipboard service for later use
        const clipboardAdapter = new GnomeClipboardAdapter();
        const notifier = new DBusNotifier();
        this._clipboardService = new ClipboardMonitorService(clipboardAdapter, notifier);

        // Scheduler will be started when app is detected as running
        log('[TFCBM] Clipboard service initialized (monitoring will start when app launches)');

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
                        } else if (methodName === 'DisableKeybinding') {
                            this._DisableKeybinding();
                            invocation.return_value(null);
                        } else if (methodName === 'EnableKeybinding') {
                            this._EnableKeybinding();
                            invocation.return_value(null);
                        } else if (methodName === 'StartMonitoring') {
                            this._StartMonitoring();
                            invocation.return_value(null);
                        } else if (methodName === 'StopMonitoring') {
                            this._StopMonitoring();
                            invocation.return_value(null);
                        } else {
                            invocation.return_dbus_error('org.freedesktop.DBus.Error.UnknownMethod', 'Unknown method');
                        }
                    } catch (e) {
                        logError(e, `TFCBM Extension: Error handling D-Bus method call ${methodName}`);
                        // Use a numeric error code directly for cross-platform compatibility
                        // instead of Gio.DBusError.Code.FAILED which is undefined in some GNOME Shell versions
                        invocation.return_dbus_error('org.freedesktop.DBus.Error.Failed', e.message || 'Unknown error');
                    }
                },
                null, // get property handler
                null  // set property handler
            );
            log(`[TFCBM] Extension D-Bus service '${EXTENSION_DBUS_NAME}' exported on path '${EXTENSION_DBUS_PATH}' with ID ${this._exportedDBusId}`);

            // Own the D-Bus name so clients can find us
            this._busNameOwnerId = Gio.bus_own_name(
                Gio.BusType.SESSION,
                EXTENSION_DBUS_NAME,
                Gio.BusNameOwnerFlags.NONE,
                null, // bus acquired callback
                (connection, name) => {
                    log(`[TFCBM] D-Bus name '${name}' acquired successfully`);
                },
                (connection, name) => {
                    log(`[TFCBM] WARNING: Lost D-Bus name '${name}'`);
                }
            );
            log(`[TFCBM] D-Bus name '${EXTENSION_DBUS_NAME}' ownership requested with ID ${this._busNameOwnerId}`);
        } catch (e) {
            logError(e, 'TFCBM: Error exporting extension D-Bus service');
        }

        // Watch for the app's D-Bus service to detect when it crashes/exits
        // If the app dies without calling StopMonitoring, we'll clean up automatically
        this._appWatchId = Gio.bus_watch_name(
            Gio.BusType.SESSION,
            'io.github.dyslechtchitect.tfcbm.ClipboardService',
            Gio.BusNameWatcherFlags.NONE,
            (connection, name, owner) => {
                log(`[TFCBM Extension] App D-Bus service appeared: ${name}`);
            },
            (connection, name) => {
                log(`[TFCBM Extension] App D-Bus service disappeared: ${name} - cleaning up`);
                // App died/crashed/exited - stop monitoring and disable keybinding
                if (this._scheduler) {
                    log('[TFCBM Extension] Auto-stopping monitoring due to app exit');
                    this._scheduler.stop();
                    this._scheduler = null;
                }
                if (!this._keybindingDisabled) {
                    try {
                        log('[TFCBM Extension] Auto-disabling keybinding due to app exit');
                        Main.wm.removeKeybinding('toggle-tfcbm-ui');
                        this._keybindingDisabled = true;
                    } catch (e) {
                        logError(e, '[TFCBM Extension] Error auto-disabling keybinding');
                    }
                }
            }
        );
        log('[TFCBM Extension] Started watching app D-Bus service for crashes/exits');

        this._reconnect();

        log('[TFCBM] Extension enable() complete - extension is now active');
    }

    disable() {
        log('[TFCBM] Extension disable() called - shutting down...');

        // Stop watching app D-Bus service
        if (this._appWatchId) {
            Gio.bus_unwatch_name(this._appWatchId);
            this._appWatchId = null;
            log('[TFCBM Extension] Stopped watching app D-Bus service');
        }

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
            Gio.bus_unown_name(this._busNameOwnerId);
            this._busNameOwnerId = null;
            log(`[TFCBM] D-Bus name '${EXTENSION_DBUS_NAME}' unowned.`);
        }

        if (this._dbus) {
            this._dbus = null;
        }
    }
}
