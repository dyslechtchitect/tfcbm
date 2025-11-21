import { Extension } from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
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
    }

    disable() {
        if (this.scheduler) {
            this.scheduler.stop();
            this.scheduler = null;
        }

        Main.wm.removeKeybinding('toggle-tfcbm-ui');
    }
}
