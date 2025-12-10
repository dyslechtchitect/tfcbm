/* extension.js
 *
 * Simple GNOME Shell extension to provide global hotkey for Popup App
 * This avoids the notification that appears with custom-keybindings on Wayland
 */

import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Meta from 'gi://Meta';
import Shell from 'gi://Shell';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

const DBUS_NAME = 'com.example.PopupApp';
const DBUS_PATH = '/com/example/PopupApp';
const DBUS_INTERFACE = 'com.example.PopupApp';

export default class PopupAppHotkeyExtension {
    constructor() {
        this._settings = null;
    }

    enable() {
        console.log('Enabling Popup App Hotkey extension');

        // Add keybinding
        Main.wm.addKeybinding(
            'popup-app-hotkey',
            this._getSettings(),
            Meta.KeyBindingFlags.NONE,
            Shell.ActionMode.NORMAL | Shell.ActionMode.OVERVIEW,
            () => this._activateApp()
        );
    }

    disable() {
        console.log('Disabling Popup App Hotkey extension');

        // Remove keybinding
        Main.wm.removeKeybinding('popup-app-hotkey');

        this._settings = null;
    }

    _getSettings() {
        if (!this._settings) {
            const GioSSS = Gio.SettingsSchemaSource;
            const schemaDir = GLib.build_filenamev([
                import.meta.url.slice(7, import.meta.url.lastIndexOf('/')),
                'schemas'
            ]);
            const schemaSource = GioSSS.new_from_directory(
                schemaDir,
                GioSSS.get_default(),
                false
            );
            const schema = schemaSource.lookup(
                'org.gnome.shell.extensions.popup-app-hotkey',
                false
            );
            this._settings = new Gio.Settings({ settings_schema: schema });
        }
        return this._settings;
    }

    _activateApp() {
        console.log('Hotkey pressed, activating Popup App');

        // Call D-Bus method to activate the app
        try {
            Gio.DBus.session.call(
                DBUS_NAME,
                DBUS_PATH,
                DBUS_INTERFACE,
                'Activate',
                null,
                null,
                Gio.DBusCallFlags.NONE,
                -1,
                null,
                (connection, result) => {
                    try {
                        connection.call_finish(result);
                        console.log('Successfully activated Popup App');
                    } catch (e) {
                        console.error(`Failed to activate Popup App: ${e.message}`);
                    }
                }
            );
        } catch (e) {
            console.error(`Error calling D-Bus: ${e.message}`);
        }
    }
}
