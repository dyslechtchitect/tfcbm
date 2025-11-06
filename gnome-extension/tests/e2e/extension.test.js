#!/usr/bin/gjs -m

imports.gi.versions.St = '13';
imports.gi.versions.Clutter = '13';

import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import St from 'gi://St';
import { ClipboardMonitorService } from '../../src/ClipboardMonitorService.js';
import { GnomeClipboardAdapter } from '../../src/adapters/GnomeClipboardAdapter.js';
import { UnixSocketNotifier } from '../../src/adapters/UnixSocketNotifier.js';

class E2ETestServer {
    constructor(socketPath) {
        this.socketPath = socketPath;
        this.messages = [];
    }

    start() {
        if (GLib.file_test(this.socketPath, GLib.FileTest.EXISTS)) {
            GLib.unlink(this.socketPath);
        }

        this.server = Gio.SocketListener.new();
        const address = Gio.UnixSocketAddress.new(this.socketPath);
        this.server.add_address(address, Gio.SocketType.STREAM,
            Gio.SocketProtocol.DEFAULT, null);

        this.listen();
    }

    listen() {
        this.server.accept_async(null, (source, result) => {
            try {
                const connection = source.accept_finish(result);
                const input = connection.get_input_stream();
                const data = input.read_bytes(4096, null).get_data();
                const message = new TextDecoder().decode(data);
                this.messages.push(JSON.parse(message.trim()));
                connection.close(null);
            } catch (e) {
            }
            this.listen();
        });
    }

    stop() {
        if (this.server) {
            this.server.close();
            try {
                GLib.unlink(this.socketPath);
            } catch (e) {
            }
        }
    }
}

print('Running E2E test...\n');

const socketPath = `/tmp/e2e-test-${Date.now()}.sock`;
const server = new E2ETestServer(socketPath);
server.start();

const clipboard = St.Clipboard.get_default();
const clipboardAdapter = new GnomeClipboardAdapter();
const notifier = new UnixSocketNotifier(socketPath);
const service = new ClipboardMonitorService(clipboardAdapter, notifier);

clipboard.set_text(St.ClipboardType.CLIPBOARD, 'e2e test message');

GLib.timeout_add(GLib.PRIORITY_DEFAULT, 100, () => {
    service.checkAndNotify().then(() => {
        GLib.timeout_add(GLib.PRIORITY_DEFAULT, 200, () => {
            const passed = server.messages.length === 1 &&
                          server.messages[0].type === 'text' &&
                          server.messages[0].content === 'e2e test message';

            print(passed ? '✓ E2E test passed\n' : '✗ E2E test failed\n');
            if (!passed) {
                print(`Received: ${JSON.stringify(server.messages)}\n`);
            }

            server.stop();
            loop.quit();
            return GLib.SOURCE_REMOVE;
        });
    });
    return GLib.SOURCE_REMOVE;
});

const loop = GLib.MainLoop.new(null, false);
loop.run();
