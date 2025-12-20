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
import { UnixSocketNotifier } from './src/adapters/UnixSocketNotifier.js';
import { PollingScheduler } from './src/PollingScheduler.js';

const DBUS_NAME = 'org.tfcbm.ClipboardManager';
const DBUS_PATH = '/org/tfcbm/ClipboardManager';
const DBUS_IFACE = 'org.tfcbm.ClipboardManager';

// Custom PanelMenu.Button that intercepts left-click to toggle UI instead of showing menu
const TFCBMIndicator = GObject.registerClass(
class TFCBMIndicator extends PanelMenu.Button {
    _init(extension) {
        super._init(0.0, 'TFCBM', false);
        this._extension = extension;
    }

    vfunc_event(event) {
        // Intercept left-click to toggle UI instead of opening menu
        if (event.type() === Clutter.EventType.BUTTON_PRESS) {
            const button = event.get_button();
            if (button === 1) { // Left click
                log('[TFCBM] Tray icon left-clicked');
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
    }

    _toggleUI() {
        log('[TFCBM] Toggling UI via DBus...');
        try {
            const timestamp = global.display.get_current_time_roundtrip();

            // Set a timeout to launch UI if DBus call doesn't respond within 500ms
            let timeoutId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 500, () => {
                log('[TFCBM] DBus call timed out, launching UI...');
                this._launchUI();
                return GLib.SOURCE_REMOVE;
            });

            Gio.DBus.session.call(
                DBUS_NAME,
                DBUS_PATH,
                DBUS_IFACE,
                'Activate',
                new GLib.Variant('(u)', [timestamp]),
                null,
                Gio.DBusCallFlags.NONE,
                -1,
                null,
                (connection, result) => {
                    // Cancel the timeout if we got a response
                    GLib.source_remove(timeoutId);

                    try {
                        connection.call_finish(result);
                        log('[TFCBM] UI activated successfully');
                    } catch (e) {
                        log('[TFCBM] Error activating UI, attempting to launch: ' + e.message);
                        // If DBus call fails, the app is not running - launch it
                        this._launchUI();
                    }
                }
            );
        } catch (e) {
            log('[TFCBM] Error calling DBus: ' + e.message);
            // If DBus call fails, the app is not running - launch it
            this._launchUI();
        }
    }

    _launchUI() {
        log('[TFCBM] Launching UI...');
        try {
            // The project path is hardcoded since the extension is installed to a different location
            const projectPath = '/home/ron/Documents/git/TFCBM';

            log(`[TFCBM] Attempting to launch from: ${projectPath}`);

            // Use the launcher script to start both server and UI
            const launchCmd = `"${projectPath}/.venv/bin/python3" "${projectPath}/launcher.py" >> /tmp/tfcbm_launcher.log 2>&1 &`;

            GLib.spawn_command_line_async(`/bin/bash -c '${launchCmd}'`);

            log('[TFCBM] UI launch command sent');
        } catch (e) {
            log('[TFCBM] Error launching UI: ' + e.message);
        }
    }

    _showSettings() {
        log('[TFCBM] Opening settings page...');
        try {
            const timestamp = global.display.get_current_time_roundtrip();
            Gio.DBus.session.call(
                DBUS_NAME,
                DBUS_PATH,
                DBUS_IFACE,
                'ShowSettings',
                new GLib.Variant('(u)', [timestamp]),
                null,
                Gio.DBusCallFlags.NONE,
                -1,
                null,
                (connection, result) => {
                    try {
                        connection.call_finish(result);
                        log('[TFCBM] Settings page opened successfully');
                    } catch (e) {
                        log('[TFCBM] Error opening settings, attempting to launch: ' + e.message);
                        // If DBus call fails, the app is not running - launch it
                        this._launchUI();
                    }
                }
            );
        } catch (e) {
            log('[TFCBM] Error calling DBus ShowSettings: ' + e.message);
            // If DBus call fails, the app is not running - launch it
            this._launchUI();
        }
    }

    _confirmExit() {
        log('[TFCBM] Confirming exit - calling _exitApp directly...');
        // Directly exit without confirmation dialog for now
        // User can cancel from menu if they change their mind
        this._exitApp();
    }

    _exitApp() {
        log('[TFCBM] Exiting application...');
        try {
            Gio.DBus.session.call(
                DBUS_NAME,
                DBUS_PATH,
                DBUS_IFACE,
                'Exit',
                null,
                null,
                Gio.DBusCallFlags.NONE,
                -1,
                null,
                (connection, result) => {
                    try {
                        connection.call_finish(result);
                        log('[TFCBM] Application exited successfully via DBus');
                    } catch (e) {
                        log('[TFCBM] Error exiting via DBus, killing processes directly: ' + e.message);
                        this._killProcesses();
                    }
                }
            );
        } catch (e) {
            log('[TFCBM] Error calling DBus Exit, killing processes directly: ' + e.message);
            this._killProcesses();
        }
    }

    _killProcesses() {
        log('[TFCBM] Killing TFCBM processes directly...');
        try {
            // Kill UI processes
            GLib.spawn_command_line_async('/bin/bash -c "pkill -f \'python.*ui/main.py\'"');
            // Kill server processes
            GLib.spawn_command_line_async('/bin/bash -c "pkill -f \'python.*tfcbm_server.py\'"');
            log('[TFCBM] Kill commands sent');
        } catch (e) {
            log('[TFCBM] Error killing processes: ' + e.message);
        }
    }

    enable() {
        log('[TFCBM] Enabling extension...');

        const clipboardAdapter = new GnomeClipboardAdapter();
        const notifier = new UnixSocketNotifier();
        const service = new ClipboardMonitorService(clipboardAdapter, notifier);

        this.scheduler = new PollingScheduler(() => {
            service.checkAndNotify();
        }, 250);

        this.scheduler.start();

        try {
            log('[TFCBM] Attempting to add keybinding...');
            this._settings = this.getSettings();
            log('[TFCBM] Got settings: ' + this._settings);
            Main.wm.addKeybinding(
                'toggle-tfcbm-ui',
                this._settings,
                0, // Gio.SettingsBindFlags.DEFAULT
                1, // Shell.ActionMode.NORMAL
                () => {
                    log('[TFCBM] Keybinding triggered!');
                    this._toggleUI();
                }
            );
            log('[TFCBM] Keybinding added successfully');
        } catch (e) {
            log('[TFCBM] Error adding keybinding: ' + e);
            log('[TFCBM] Error stack: ' + e.stack);
        }

        // Create system tray indicator
        try {
            log('[TFCBM] Creating tray indicator...');
            this._indicator = new TFCBMIndicator(this);

            // Load custom icon from resources
            const iconPath = `${this.metadata.path}/../resouces/tfcbm.svg`;
            let icon;

            if (GLib.file_test(iconPath, GLib.FileTest.EXISTS)) {
                log('[TFCBM] Using custom icon from: ' + iconPath);
                const gicon = Gio.icon_new_for_string(iconPath);
                icon = new St.Icon({
                    gicon: gicon,
                    style_class: 'system-status-icon',
                });
            } else {
                log('[TFCBM] Custom icon not found, using fallback');
                icon = new St.Icon({
                    icon_name: 'edit-paste-symbolic',
                    style_class: 'system-status-icon',
                });
            }

            this._indicator.add_child(icon);

            // Make the icon reactive and add click handler
            icon.reactive = true;
            icon.connect('button-press-event', (actor, event) => {
                const button = event.get_button();
                log(`[TFCBM] Icon clicked, button=${button}`);
                if (button === 1) { // Left click
                    log('[TFCBM] Left click on icon, toggling UI');
                    this._toggleUI();
                    return Clutter.EVENT_STOP;
                }
                return Clutter.EVENT_PROPAGATE;
            });

            // Create popup menu (right-click)
            const settingsItem = new PopupMenu.PopupMenuItem('Settings');
            settingsItem.connect('activate', () => {
                log('[TFCBM] Settings menu item clicked');
                this._showSettings();
            });
            this._indicator.menu.addMenuItem(settingsItem);

            // Add separator
            this._indicator.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

            const exitItem = new PopupMenu.PopupMenuItem('Exit');
            exitItem.connect('activate', () => {
                log('[TFCBM] Exit menu item clicked');
                this._confirmExit();
            });
            this._indicator.menu.addMenuItem(exitItem);

            // Add to panel
            Main.panel.addToStatusArea('tfcbm-indicator', this._indicator);
            log('[TFCBM] Tray indicator added successfully');
        } catch (e) {
            log('[TFCBM] Error creating tray indicator: ' + e);
            log('[TFCBM] Stack: ' + e.stack);
        }
    }

    disable() {
        if (this.scheduler) {
            this.scheduler.stop();
            this.scheduler = null;
        }

        if (this._settings) {
            Main.wm.removeKeybinding('toggle-tfcbm-ui');
            this._settings = null;
        }

        if (this._indicator) {
            this._indicator.destroy();
            this._indicator = null;
        }

        log('[TFCBM] Extension disabled');
    }
}
