import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import { NotificationPort } from '../domain/NotificationPort.js';

const DBUS_NAME = 'io.github.dyslechtchitect.tfcbm.ClipboardService';
const DBUS_PATH = '/io/github/dyslechtchitect/tfcbm/ClipboardService';
const DBUS_IFACE = 'io.github.dyslechtchitect.tfcbm.ClipboardService';

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
            log(`[TFCBM DBusNotifier] Sending clipboard event: ${event.type}, data_length=${event.data ? event.data.length : 0}`);

            return new Promise((resolve) => {
                Gio.DBus.session.call(
                    DBUS_NAME,
                    DBUS_PATH,
                    DBUS_IFACE,
                    'OnClipboardChange',
                    new GLib.Variant('(s)', [eventData]),
                    null,
                    Gio.DBusCallFlags.NONE,
                    5000, // 5 second timeout for large images/files
                    null,
                    (connection, result) => {
                        try {
                            connection.call_finish(result);
                            this._lastFailTime = 0; // Reset on success
                            log(`[TFCBM DBusNotifier] Successfully sent clipboard event: ${event.type}`);
                            resolve(true);
                        } catch (e) {
                            // Log errors for debugging
                            logError(e, `[TFCBM DBusNotifier] DBus send failed for type ${event.type}`);
                            this._lastFailTime = Date.now(); // Mark failure time
                            resolve(false);
                        }
                    }
                );
            });
        } catch (e) {
            logError(e, '[TFCBM DBusNotifier] Exception during send');
            return false;
        }
    }
}
