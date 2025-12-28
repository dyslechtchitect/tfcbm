import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import { NotificationPort } from '../domain/NotificationPort.js';

const DBUS_NAME = 'org.tfcbm.ClipboardManager';
const DBUS_PATH = '/org/tfcbm/ClipboardService';
const DBUS_IFACE = 'org.tfcbm.ClipboardService';

/**
 * DBus-based notifier that sends clipboard events to TFCBM application
 * This is compliant with GNOME extension standards as it only communicates
 * with external apps via DBus, without launching or managing processes
 */
export class DBusNotifier extends NotificationPort {
    constructor() {
        super();
        this._lastFailTime = 0;
        this._backoffTime = 500; // Wait 500ms after failures before retrying
    }

    async send(event) {
        // Backoff: Only after failures, don't block successful sends
        const now = Date.now();
        if (this._lastFailTime > 0 && now - this._lastFailTime < this._backoffTime) {
            return false;
        }

        try {
            const eventData = JSON.stringify(event.toJSON());

            return new Promise((resolve) => {
                Gio.DBus.session.call(
                    DBUS_NAME,
                    DBUS_PATH,
                    DBUS_IFACE,
                    'OnClipboardChange',
                    new GLib.Variant('(s)', [eventData]),
                    null,
                    Gio.DBusCallFlags.NONE,
                    1000, // 1 second timeout
                    null,
                    (connection, result) => {
                        try {
                            connection.call_finish(result);
                            this._lastFailTime = 0; // Reset on success
                            resolve(true);
                        } catch (e) {
                            // App not running or method doesn't exist - this is OK
                            // Don't log errors to avoid spamming journalctl
                            this._lastFailTime = Date.now(); // Mark failure time
                            resolve(false);
                        }
                    }
                );
            });
        } catch (e) {
            return false;
        }
    }
}
