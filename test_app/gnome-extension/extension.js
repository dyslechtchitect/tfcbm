import { Extension } from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import St from 'gi://St';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

const APP_ID = 'org.example.ShortcutRecorder';
const DBUS_NAME = APP_ID;
const DBUS_PATH = '/org/example/ShortcutRecorder';

export default class ShortcutRecorderExtension extends Extension {
    constructor(metadata) {
        super(metadata);
        this._settings = null;
        this._indicator = null;
    }

    _launchOrFocusApp() {
        log('[ShortcutRecorder] Launching or focusing app...');

        // First, try to focus existing window via DBus
        Gio.DBus.session.call(
            DBUS_NAME,
            DBUS_PATH,
            'org.gtk.Actions',
            'Activate',
            new GLib.Variant('(sava{sv})', ['show-window', [], {}]),
            null,
            Gio.DBusCallFlags.NONE,
            -1,
            null,
            (connection, result) => {
                try {
                    connection.call_finish(result);
                    log('[ShortcutRecorder] Window toggled successfully');
                } catch (e) {
                    // App not running, launch it
                    log('[ShortcutRecorder] App not running, launching...');
                    this._launchApp();
                }
            }
        );
    }

    _launchApp() {
        try {
            // Get the directory where the extension is installed
            const extensionPath = this.metadata.path;
            const appPath = extensionPath.replace('/gnome-shell/extensions/' + this.metadata.uuid, '');

            log(`[ShortcutRecorder] Attempting to launch from: ${appPath}`);

            // Launch the app using run.sh or main.py
            GLib.spawn_async(
                appPath,
                ['bash', appPath + '/run.sh'],
                null,
                GLib.SpawnFlags.SEARCH_PATH,
                null
            );

            log('[ShortcutRecorder] Launch command sent');
        } catch (e) {
            log('[ShortcutRecorder] Error launching app: ' + e.message);
        }
    }

    _toggleWindow() {
        log('[ShortcutRecorder] Keyboard shortcut pressed!');
        this._launchOrFocusApp();
    }

    enable() {
        log('[ShortcutRecorder] Enabling extension...');

        try {
            this._settings = this.getSettings();

            // Create the system tray indicator
            this._indicator = new PanelMenu.Button(0.0, 'Shortcut Recorder', false);

            // Create icon using symbolic icon
            let icon = new St.Icon({
                icon_name: 'input-keyboard-symbolic',
                style_class: 'system-status-icon',
            });

            this._indicator.add_child(icon);

            // Connect click handler
            this._indicator.connect('button-press-event', () => {
                log('[ShortcutRecorder] Tray icon clicked!');
                this._launchOrFocusApp();
                return true;
            });

            // Add to the panel
            log('[ShortcutRecorder] Adding indicator to panel...');
            Main.panel.addToStatusArea('shortcut-recorder-indicator', this._indicator);
            log('[ShortcutRecorder] Indicator added to panel successfully!');

            // Add the keybinding
            log('[ShortcutRecorder] Adding keybinding...');
            Main.wm.addKeybinding(
                'toggle-shortcut-recorder',
                this._settings,
                0, // Gio.SettingsBindFlags.DEFAULT
                1, // Shell.ActionMode.NORMAL
                () => {
                    log('[ShortcutRecorder] Keybinding triggered!');
                    this._toggleWindow();
                }
            );
            log('[ShortcutRecorder] Keybinding added successfully!');

            log('[ShortcutRecorder] === Extension enabled successfully ===');
            log('[ShortcutRecorder] Tray icon should be visible in top panel');
            log('[ShortcutRecorder] Press Ctrl+Shift+K to toggle the window');
        } catch (e) {
            log('[ShortcutRecorder] Error enabling extension: ' + e);
            log('[ShortcutRecorder] Stack: ' + e.stack);
        }
    }

    disable() {
        log('[ShortcutRecorder] Disabling extension...');

        if (this._settings) {
            Main.wm.removeKeybinding('toggle-shortcut-recorder');
            this._settings = null;
        }

        if (this._indicator) {
            this._indicator.destroy();
            this._indicator = null;
        }

        log('[ShortcutRecorder] Extension disabled');
    }
}
