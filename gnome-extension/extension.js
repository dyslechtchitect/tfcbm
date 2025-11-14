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

        Main.wm.addKeybinding(
            'toggle-tfcbm-ui',
            this.getSettings(),
            0, // Gio.SettingsBindFlags.DEFAULT
            1, // Shell.ActionMode.NORMAL
            () => this._toggleUI()
        );
    }

    disable() {
        if (this.scheduler) {
            this.scheduler.stop();
            this.scheduler = null;
        }

        Main.wm.removeKeybinding('toggle-tfcbm-ui');
    }
}
