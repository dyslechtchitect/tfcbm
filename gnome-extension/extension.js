import { Extension } from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import { ClipboardMonitorService } from './src/ClipboardMonitorService.js';
import { GnomeClipboardAdapter } from './src/adapters/GnomeClipboardAdapter.js';
import { UnixSocketNotifier } from './src/adapters/UnixSocketNotifier.js';
import { PollingScheduler } from './src/PollingScheduler.js';

const APP_ID = 'org.tfcbm.ClipboardManager.desktop';

export default class ClipboardMonitorExtension extends Extension {
    constructor(metadata) {
        super(metadata);
    }

    _toggleUI() {
        log('[TFCBM] Toggling UI...');
        let app = Main.AppSystem.get_default().lookup_app(APP_ID);
        if (app) {
            app.activate();
        } else {
            log(`[TFCBM] App with ID ${APP_ID} not found.`);
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
            const settings = this.getSettings();
            log('[TFCBM] Got settings: ' + settings);
            Main.wm.addKeybinding(
                'toggle-tfcbm-ui',
                settings,
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
