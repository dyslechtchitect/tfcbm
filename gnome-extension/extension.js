import { Extension } from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import Gio from 'gi://Gio';
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
            // Load settings from extension's schemas directory
            log('[TFCBM] Extension dir: ' + this.dir.get_path());
            const schemaDir = this.dir.get_child('schemas');
            log('[TFCBM] Schema dir: ' + schemaDir.get_path());
            const schemaSource = Gio.SettingsSchemaSource.new_from_directory(
                schemaDir.get_path(),
                Gio.SettingsSchemaSource.get_default(),
                false
            );
            log('[TFCBM] Schema source created');
            const schema = schemaSource.lookup('org.gnome.shell.extensions.simple-clipboard', false);
            log('[TFCBM] Schema lookup result: ' + schema);
            if (!schema) {
                throw new Error('Schema not found');
            }
            this._settings = new Gio.Settings({ settings_schema: schema });
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
