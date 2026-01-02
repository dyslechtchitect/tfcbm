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
import { ClipboardMonitorService } from './src/ClipboardMonitorService.js';
import { GnomeClipboardAdapter } from './src/adapters/GnomeClipboardAdapter.js';
import { DBusNotifier } from './src/adapters/DBusNotifier.js';
import { PollingScheduler } from './src/PollingScheduler.js';
import { SidePanelManager } from './src/SidePanelManager.js';

const DBUS_NAME = 'io.github.dyslechtchitect.tfcbm';
const DBUS_PATH = '/org/tfcbm/ClipboardService';
const DBUS_IFACE = 'org.tfcbm.ClipboardService';

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
        <method name="GetUIMode">
            <arg type="s" name="mode" direction="out"/>
            <arg type="s" name="alignment" direction="out"/>
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
        this._flatpakCheckTimeout = null;
        this._uiMode = 'windowed';  // 'windowed' or 'sidepanel'
        this._uiAlignment = 'right'; // 'left' or 'right'
        this._sidePanelManager = null;
    }

    _launchApp() {
        try {
            const tfcbmPath = this._settings.get_string('tfcbm-path');
            if (!tfcbmPath || !GLib.file_test(tfcbmPath, GLib.FileTest.IS_DIR)) {
                logError(new Error(`TFCBM path not configured or invalid: ${tfcbmPath}`));
                return;
            }

            const command = [`${tfcbmPath}/install.sh`, 'run'];
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

    _fetchUIMode() {
        if (!this._dbus) {
            log('[TFCBM] Cannot fetch UI mode: DBus not connected');
            return;
        }

        try {
            this._dbus.GetUIModeRemote((result, error) => {
                if (error) {
                    logError(error, '[TFCBM] Failed to get UI mode');
                    return;
                }

                const [mode, alignment] = result;
                this._uiMode = mode;
                this._uiAlignment = alignment;
                log(`[TFCBM] UI Mode fetched: ${mode}, alignment: ${alignment}`);

                // Initialize side panel if in sidepanel mode
                if (mode === 'sidepanel') {
                    this._initializeSidePanel();
                }
            });
        } catch (e) {
            logError(e, '[TFCBM] Error calling GetUIMode');
        }
    }

    async _initializeSidePanel() {
        if (this._sidePanelManager) {
            log('[TFCBM] Side panel already initialized');
            return;
        }

        try {
            log('[TFCBM] Initializing side panel...');
            this._sidePanelManager = new SidePanelManager(this._uiAlignment);
            const success = await this._sidePanelManager.initialize();

            if (success) {
                log('[TFCBM] Side panel initialized successfully');
            } else {
                logError(new Error('Initialization failed'), '[TFCBM] Side panel');
                this._sidePanelManager = null;
            }
        } catch (e) {
            logError(e, '[TFCBM] Failed to initialize side panel');
            this._sidePanelManager = null;
        }
    }

    _toggleUI() {
        if (this._dbusOwner) {
            try {
                if (this._uiMode === 'sidepanel') {
                    // Side panel mode - toggle panel
                    if (this._sidePanelManager) {
                        this._sidePanelManager.toggle();
                        log('[TFCBM] Toggled side panel');
                    } else {
                        log('[TFCBM] Side panel not initialized, initializing...');
                        this._initializeSidePanel().then(() => {
                            if (this._sidePanelManager) {
                                this._sidePanelManager.show();
                            }
                        });
                    }
                } else {
                    // Windowed mode - activate window
                    const timestamp = global.display.get_current_time_roundtrip();
                    this._dbus.ActivateRemote(timestamp);
                }
            } catch (e) {
                logError(e, 'Failed to activate TFCBM UI');
                // Check if app was uninstalled before trying to launch
                this._checkFlatpakInstalled();
                this._launchApp();
            }
        } else {
            // Check if app is installed before trying to launch
            this._checkFlatpakInstalled();
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

                    // Fetch UI mode once connected
                    if (this._dbusOwner) {
                        this._fetchUIMode();
                    }
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

    _checkFlatpakInstalled() {
        // Check if the Flatpak is still installed
        // If not, disable this extension (cleanup after uninstall)
        try {
            GLib.spawn_command_line_sync('flatpak list --app');
            const [ok, stdout] = GLib.spawn_command_line_sync('flatpak list --app');
            if (ok) {
                const output = new TextDecoder().decode(stdout);
                if (!output.includes('io.github.dyslechtchitect.tfcbm')) {
                    // Flatpak was uninstalled, disable this extension
                    log('[TFCBM] Flatpak uninstalled, disabling extension...');
                    GLib.spawn_command_line_async('gnome-extensions disable tfcbm-clipboard-monitor@github.com');
                }
            }
        } catch (e) {
            // Ignore errors - might not have flatpak command
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
                1, // Shell.ActionMode.NORMAL
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
        // Initialize clipboard monitoring
        const clipboardAdapter = new GnomeClipboardAdapter();
        const notifier = new DBusNotifier();
        const service = new ClipboardMonitorService(clipboardAdapter, notifier);

        this._scheduler = new PollingScheduler(() => {
            service.checkAndNotify();
        }, 250);

        this._scheduler.start();

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

        this._reconnect();

        // Set initial icon visibility (will be hidden if app not running)
        this._updateIconStyle();

        // Check immediately on enable
        this._checkFlatpakInstalled();

        // Check periodically if Flatpak is still installed (every 10 seconds)
        // This ensures the extension auto-disables quickly if the Flatpak is uninstalled
        this._flatpakCheckTimeout = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 10, () => {
            this._checkFlatpakInstalled();
            return GLib.SOURCE_CONTINUE; // Keep running
        });
    }

    disable() {
        // Destroy side panel if active
        if (this._sidePanelManager) {
            this._sidePanelManager.destroy();
            this._sidePanelManager = null;
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

        // Remove tray indicator
        if (this._indicator) {
            this._indicator.destroy();
            this._indicator = null;
            this._icon = null;
        }

        // Stop Flatpak check timeout
        if (this._flatpakCheckTimeout) {
            GLib.source_remove(this._flatpakCheckTimeout);
            this._flatpakCheckTimeout = null;
        }

        // Disconnect DBus owner watch
        if (this._dbusOwnerWatchId) {
            Gio.DBus.session.signal_unsubscribe(this._dbusOwnerWatchId);
            this._dbusOwnerWatchId = null;
        }
        if (this._dbus) {
            this._dbus = null;
        }
    }
}
