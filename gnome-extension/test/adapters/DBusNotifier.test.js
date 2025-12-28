import { describe, it, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert';
import { FakeGio, FakeVariant } from '../fakes/FakeGnomeAPIs.js';
import { ClipboardEvent } from '../../src/domain/ClipboardEvent.js';

// Testable version of DBusNotifier that accepts dependencies
class TestableDBusNotifier {
    constructor(Gio, GLibVariant) {
        this.Gio = Gio;
        this.GLibVariant = GLibVariant;
        this._lastFailTime = 0;
        this._backoffTime = 500;
    }

    async send(event) {
        const now = Date.now();
        if (this._lastFailTime > 0 && now - this._lastFailTime < this._backoffTime) {
            return false;
        }

        try {
            const eventData = JSON.stringify(event.toJSON());

            return new Promise((resolve) => {
                this.Gio.DBus.session.call(
                    'org.tfcbm.ClipboardManager',
                    '/org/tfcbm/ClipboardService',
                    'org.tfcbm.ClipboardService',
                    'OnClipboardChange',
                    new this.GLibVariant('(s)', [eventData]),
                    null,
                    this.Gio.DBusCallFlags.NONE,
                    1000,
                    null,
                    (connection, result) => {
                        try {
                            result.call_finish();
                            this._lastFailTime = 0;
                            resolve(true);
                        } catch (e) {
                            this._lastFailTime = Date.now();
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

describe('DBusNotifier', () => {
    let notifier;
    let dbus;

    beforeEach(() => {
        dbus = FakeGio.DBus.session;
        dbus.clear();
        dbus.setShouldSucceed(true);
        notifier = new TestableDBusNotifier(FakeGio, FakeVariant);
    });

    afterEach(() => {
        dbus.clear();
    });

    describe('send', () => {
        it('should send text event over DBus', async () => {
            const event = new ClipboardEvent('text', 'Hello World');

            const result = await notifier.send(event);

            assert.strictEqual(result, true);
            assert.strictEqual(dbus.getCalls().length, 1);

            const call = dbus.getLastCall();
            assert.strictEqual(call.busName, 'org.tfcbm.ClipboardManager');
            assert.strictEqual(call.objectPath, '/org/tfcbm/ClipboardService');
            assert.strictEqual(call.interfaceName, 'org.tfcbm.ClipboardService');
            assert.strictEqual(call.methodName, 'OnClipboardChange');
        });

        it('should send file event over DBus', async () => {
            const event = new ClipboardEvent('file', 'file:///home/user/test.txt');

            const result = await notifier.send(event);

            assert.strictEqual(result, true);
            const call = dbus.getLastCall();
            const eventData = JSON.parse(call.parameters[0]);
            assert.strictEqual(eventData.type, 'file');
            assert.strictEqual(eventData.content, 'file:///home/user/test.txt');
        });

        it('should send image event over DBus', async () => {
            const imageData = JSON.stringify({ mimeType: 'image/png', data: 'base64data' });
            const event = new ClipboardEvent('image/screenshot', imageData);

            const result = await notifier.send(event);

            assert.strictEqual(result, true);
            const call = dbus.getLastCall();
            const eventData = JSON.parse(call.parameters[0]);
            assert.strictEqual(eventData.type, 'image/screenshot');
        });

        it('should send formatted text event with metadata', async () => {
            const event = new ClipboardEvent('text', 'Hello', '<b>Hello</b>', 'html');

            const result = await notifier.send(event);

            assert.strictEqual(result, true);
            const call = dbus.getLastCall();
            const eventData = JSON.parse(call.parameters[0]);
            assert.strictEqual(eventData.type, 'text');
            assert.strictEqual(eventData.content, 'Hello');
            assert.strictEqual(eventData.formatted_content, '<b>Hello</b>');
            assert.strictEqual(eventData.format_type, 'html');
        });

        it('should not include timestamp in sent event', async () => {
            const event = new ClipboardEvent('text', 'Test');

            await notifier.send(event);

            const call = dbus.getLastCall();
            const eventData = JSON.parse(call.parameters[0]);
            assert.strictEqual(eventData.timestamp, undefined);
        });

        it('should set timeout to 1000ms', async () => {
            const event = new ClipboardEvent('text', 'Test');

            await notifier.send(event);

            const call = dbus.getLastCall();
            assert.strictEqual(call.timeout, 1000);
        });
    });

    describe('error handling', () => {
        it('should return false when DBus call fails', async () => {
            dbus.setShouldSucceed(false);
            const event = new ClipboardEvent('text', 'Test');

            const result = await notifier.send(event);

            assert.strictEqual(result, false);
        });

        it('should not throw when DBus call fails', async () => {
            dbus.setShouldSucceed(false);
            const event = new ClipboardEvent('text', 'Test');

            // Should not throw
            const result = await notifier.send(event);

            assert.strictEqual(result, false);
        });
    });

    describe('backoff mechanism', () => {
        it('should set backoff after failure', async () => {
            dbus.setShouldSucceed(false);
            const event = new ClipboardEvent('text', 'Test');

            const result = await notifier.send(event);

            assert.strictEqual(result, false);
            assert.ok(notifier._lastFailTime > 0);
        });

        it('should skip sends during backoff period', async () => {
            dbus.setShouldSucceed(false);
            const event = new ClipboardEvent('text', 'Test');

            // First call fails
            await notifier.send(event);

            // Second call should be skipped (within 500ms backoff)
            dbus.clear();
            dbus.setShouldSucceed(true);
            const result = await notifier.send(event);

            assert.strictEqual(result, false);
            assert.strictEqual(dbus.getCalls().length, 0); // No DBus call made
        });

        it('should reset backoff on successful send', async () => {
            const event = new ClipboardEvent('text', 'Test');

            // Successful send
            await notifier.send(event);

            assert.strictEqual(notifier._lastFailTime, 0);
        });

        it('should allow sends after backoff period', async (t) => {
            dbus.setShouldSucceed(false);
            const event = new ClipboardEvent('text', 'Test');

            // First call fails
            await notifier.send(event);

            // Mock time passing by directly setting _lastFailTime
            notifier._lastFailTime = Date.now() - 600; // 600ms ago

            // Should allow the call now
            dbus.clear();
            dbus.setShouldSucceed(true);
            const result = await notifier.send(event);

            assert.strictEqual(result, true);
            assert.strictEqual(dbus.getCalls().length, 1);
        });

        it('should have 500ms backoff time', () => {
            assert.strictEqual(notifier._backoffTime, 500);
        });
    });

    describe('serialization', () => {
        it('should properly serialize event to JSON string', async () => {
            const event = new ClipboardEvent('text', 'Test Content');

            await notifier.send(event);

            const call = dbus.getLastCall();
            assert.strictEqual(typeof call.parameters[0], 'string');

            // Should be valid JSON
            const parsed = JSON.parse(call.parameters[0]);
            assert.strictEqual(parsed.type, 'text');
            assert.strictEqual(parsed.content, 'Test Content');
        });

        it('should handle special characters in content', async () => {
            const specialContent = 'Test\nNew Line\tTab"Quote\'Single';
            const event = new ClipboardEvent('text', specialContent);

            await notifier.send(event);

            const call = dbus.getLastCall();
            const parsed = JSON.parse(call.parameters[0]);
            assert.strictEqual(parsed.content, specialContent);
        });

        it('should handle unicode content', async () => {
            const unicodeContent = 'Hello 世界 🌍 مرحبا';
            const event = new ClipboardEvent('text', unicodeContent);

            await notifier.send(event);

            const call = dbus.getLastCall();
            const parsed = JSON.parse(call.parameters[0]);
            assert.strictEqual(parsed.content, unicodeContent);
        });
    });
});
