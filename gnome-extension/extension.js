import { Extension } from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import St from 'gi://St';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import { ClipboardMonitorService } from './src/ClipboardMonitorService.js';
import { GnomeClipboardAdapter } from './src/adapters/GnomeClipboardAdapter.js';
import { UnixSocketNotifier } from './src/adapters/UnixSocketNotifier.js';
import { PollingScheduler } from './src/PollingScheduler.js';

const DBUS_NAME = 'org.tfcbm.ClipboardManager';
const DBUS_PATH = '/org/tfcbm/ClipboardManager';
const DBUS_IFACE = 'org.tfcbm.ClipboardManager';

export default class ClipboardMonitorExtension extends Extension {
    constructor(metadata) {
        super(metadata);
        this._indicator = null;
    }

    _toggleUI() {
        log('[TFCBM] Toggling UI via DBus...');
        try {
            const timestamp = global.display.get_current_time_roundtrip();
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
                    try {
                        connection.call_finish(result);
                        log('[TFCBM] UI activated successfully');
                    } catch (e) {
                        log('[TFCBM] Error activating UI: ' + e.message);
                    }
                }
            );
        } catch (e) {
            log('[TFCBM] Error calling DBus: ' + e.message);
        }
    }

    _launchUI() {
        log('[TFCBM] Launching UI...');
        try {
            const extensionPath = this.metadata.path;
            const projectPath = extensionPath.replace('/gnome-extension', '');

            log(`[TFCBM] Attempting to launch from: ${projectPath}`);

            // Launch using the venv python
            GLib.spawn_async(
                projectPath,
                ['/bin/bash', '-c', `cd "${projectPath}" && .venv/bin/python3 ui/main.py`],
                null,
                GLib.SpawnFlags.SEARCH_PATH,
                null
            );

            log('[TFCBM] UI launch command sent');
        } catch (e) {
            log('[TFCBM] Error launching UI: ' + e.message);
        }
    }

    _showAbout() {
        log('[TFCBM] Showing about dialog...');
        // We'll trigger the UI and let it show the about dialog
        this._toggleUI();
    }

    _openSettings() {
        log('[TFCBM] Opening settings...');
        // We'll trigger the UI to show settings page
        // The UI can detect this via a DBus call parameter in the future
        this._toggleUI();
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
            this._indicator = new PanelMenu.Button(0.0, 'TFCBM', false);

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

            // Create popup menu (right-click)
            const settingsItem = new PopupMenu.PopupMenuItem('Settings');
            settingsItem.connect('activate', () => {
                log('[TFCBM] Settings menu item clicked');
                this._openSettings();
            });
            this._indicator.menu.addMenuItem(settingsItem);

            const aboutItem = new PopupMenu.PopupMenuItem('About');
            aboutItem.connect('activate', () => {
                log('[TFCBM] About menu item clicked');
                this._showAbout();
            });
            this._indicator.menu.addMenuItem(aboutItem);

            // Left-click handler - toggle UI
            this._indicator.connect('button-press-event', (actor, event) => {
                const button = event.get_button();
                if (button === 1) { // Left click
                    log('[TFCBM] Tray icon left-clicked');
                    this._toggleUI();
                    return true;
                }
                return false;
            });

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
