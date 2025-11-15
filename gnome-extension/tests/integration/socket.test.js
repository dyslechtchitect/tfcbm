#!/usr/bin/gjs -m

import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import { UnixSocketNotifier } from '../../src/adapters/UnixSocketNotifier.js';
import { ClipboardEvent } from '../../src/domain/ClipboardEvent.js';

class TestSocketServer {
    constructor(socketPath) {
        this.socketPath = socketPath;
        this.receivedMessages = [];
        this.server = null;
    }

    start() {
        return new Promise((resolve) => {
            try {
                if (GLib.file_test(this.socketPath, GLib.FileTest.EXISTS)) {
                    GLib.unlink(this.socketPath);
                }

                this.server = Gio.SocketListener.new();
                const address = Gio.UnixSocketAddress.new(this.socketPath);
                this.server.add_address(
                    address,
                    Gio.SocketType.STREAM,
                    Gio.SocketProtocol.DEFAULT,
                    null
                );

                this.listenForConnections();
                resolve();
            } catch (e) {
                print(`Server error: ${e.message}`);
                resolve();
            }
        });
    }

    listenForConnections() {
        this.server.accept_async(null, (source, result) => {
            try {
                const connection = source.accept_finish(result);
                const input = connection.get_input_stream();
                const data = input.read_bytes(4096, null).get_data();
                const message = new TextDecoder().decode(data);

                this.receivedMessages.push(JSON.parse(message.trim()));
                connection.close(null);
            } catch (e) {
                print(`Accept error: ${e.message}`);
            }

            this.listenForConnections();
        });
    }

    stop() {
        if (this.server) {
            this.server.close();
            try {
                GLib.unlink(this.socketPath);
            } catch (e) {}
        }
    }
}

const socketPath = `/tmp/test-clipboard-${Date.now()}.sock`;
const server = new TestSocketServer(socketPath);

print('Starting socket integration test...\n');

server
    .start()
    .then(() => {
        const notifier = new UnixSocketNotifier(socketPath);
        const event = new ClipboardEvent('text', 'integration test');

        return notifier.send(event);
    })
    .then((sent) => {
        GLib.timeout_add(GLib.PRIORITY_DEFAULT, 100, () => {
            const success =
                server.receivedMessages.length === 1 &&
                server.receivedMessages[0].type === 'text' &&
                server.receivedMessages[0].content === 'integration test';

            print(
                success
                    ? '✓ Socket integration test passed\n'
                    : '✗ Socket integration test failed\n'
            );

            server.stop();
            return GLib.SOURCE_REMOVE;
        });

        return GLib.SOURCE_REMOVE;
    });

const loop = GLib.MainLoop.new(null, false);
GLib.timeout_add(GLib.PRIORITY_DEFAULT, 500, () => {
    loop.quit();
    return GLib.SOURCE_REMOVE;
});
loop.run();
