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

const DBUS_NAME = 'org.tfcbm.ClipboardManager';
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
        this._dbus = null;
        this._dbusOwner = null;
        this._dbusOwnerWatchId = null;
        this._icon = null;
        this._flatpakCheckTimeout = null;
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

    _toggleUI() {
        if (this._dbusOwner) {
            try {
                const timestamp = global.display.get_current_time_roundtrip();
                this._dbus.ActivateRemote(timestamp);
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
        if (!this._icon) return;

        if (this._dbusOwner) {
            this._icon.remove_style_class_name('disabled');
        } else {
            this._icon.add_style_class_name('disabled');
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

        Gio.DBusProxy.new_for_bus(
            Gio.BusType.SESSION,
            Gio.DBusProxyFlags.NONE,
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

    _checkFlatpakInstalled() {
        // Check if the Flatpak is still installed
        // If not, disable this extension (cleanup after uninstall)
        try {
            GLib.spawn_command_line_sync('flatpak list --app');
            const [ok, stdout] = GLib.spawn_command_line_sync('flatpak list --app');
            if (ok) {
                const output = new TextDecoder().decode(stdout);
                if (!output.includes('org.tfcbm.ClipboardManager')) {
                    // Flatpak was uninstalled, disable this extension
                    log('[TFCBM] Flatpak uninstalled, disabling extension...');
                    GLib.spawn_command_line_async('gnome-extensions disable tfcbm-clipboard-monitor@github.com');
                }
            }
        } catch (e) {
            // Ignore errors - might not have flatpak command
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
            this._settings = this.getSettings();
            Main.wm.addKeybinding(
                'toggle-tfcbm-ui',
                this._settings,
                0, // Gio.SettingsBindFlags.DEFAULT
                1, // Shell.ActionMode.NORMAL
                () => {
                    this._toggleUI();
                }
            );
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
        // Stop clipboard monitoring
        if (this._scheduler) {
            this._scheduler.stop();
            this._scheduler = null;
        }

        // Remove keybinding
        if (this._settings) {
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
