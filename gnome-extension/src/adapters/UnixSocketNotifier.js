import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import { NotificationPort } from '../domain/NotificationPort.js';

export class UnixSocketNotifier extends NotificationPort {
    constructor(socketPath = null) {
        super();
        this.socketPath = socketPath ||
            GLib.build_filenamev([GLib.get_user_runtime_dir(), 'simple-clipboard.sock']);
    }

    async send(event) {
        try {
            const message = JSON.stringify(event.toJSON()) + '\n';
            const client = new Gio.SocketClient();
            const address = Gio.UnixSocketAddress.new(this.socketPath);

            return new Promise((resolve) => {
                client.connect_async(address, null, (source, result) => {
                    try {
                        const connection = source.connect_finish(result);
                        const output = connection.get_output_stream();
                        output.write_all(message, null);
                        connection.close(null);
                        resolve(true);
                    } catch (e) {
                        resolve(false);
                    }
                });
            });
        } catch (e) {
            return false;
        }
    }
}
