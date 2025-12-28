import { describe, it } from 'node:test';
import assert from 'node:assert';
import { ClipboardEvent } from '../../src/domain/ClipboardEvent.js';

describe('ClipboardEvent', () => {
    describe('constructor', () => {
        it('should create event with type and content', () => {
            const event = new ClipboardEvent('text', 'Hello World');

            assert.strictEqual(event.type, 'text');
            assert.strictEqual(event.content, 'Hello World');
            assert.strictEqual(event.formattedContent, null);
            assert.strictEqual(event.formatType, null);
            assert.ok(event.timestamp > 0);
        });

        it('should create event with formatted content', () => {
            const event = new ClipboardEvent(
                'text',
                'Hello',
                '<b>Hello</b>',
                'html'
            );

            assert.strictEqual(event.type, 'text');
            assert.strictEqual(event.content, 'Hello');
            assert.strictEqual(event.formattedContent, '<b>Hello</b>');
            assert.strictEqual(event.formatType, 'html');
        });

        it('should create file event', () => {
            const event = new ClipboardEvent('file', 'file:///home/user/test.txt');

            assert.strictEqual(event.type, 'file');
            assert.strictEqual(event.content, 'file:///home/user/test.txt');
        });

        it('should create image event', () => {
            const imageData = JSON.stringify({
                mimeType: 'image/png',
                data: 'base64data'
            });
            const event = new ClipboardEvent('image/screenshot', imageData);

            assert.strictEqual(event.type, 'image/screenshot');
            assert.strictEqual(event.content, imageData);
        });

        it('should set timestamp on creation', () => {
            const before = Date.now();
            const event = new ClipboardEvent('text', 'test');
            const after = Date.now();

            assert.ok(event.timestamp >= before);
            assert.ok(event.timestamp <= after);
        });
    });

    describe('equals', () => {
        it('should return true for identical events', () => {
            const event1 = new ClipboardEvent('text', 'Hello');
            const event2 = new ClipboardEvent('text', 'Hello');

            assert.strictEqual(event1.equals(event2), true);
        });

        it('should return false for different types', () => {
            const event1 = new ClipboardEvent('text', 'Hello');
            const event2 = new ClipboardEvent('file', 'Hello');

            assert.strictEqual(event1.equals(event2), false);
        });

        it('should return false for different content', () => {
            const event1 = new ClipboardEvent('text', 'Hello');
            const event2 = new ClipboardEvent('text', 'World');

            assert.strictEqual(event1.equals(event2), false);
        });

        it('should compare formatted content', () => {
            const event1 = new ClipboardEvent('text', 'Hello', '<b>Hello</b>', 'html');
            const event2 = new ClipboardEvent('text', 'Hello', '<b>Hello</b>', 'html');

            assert.strictEqual(event1.equals(event2), true);
        });

        it('should return false for different formatted content', () => {
            const event1 = new ClipboardEvent('text', 'Hello', '<b>Hello</b>', 'html');
            const event2 = new ClipboardEvent('text', 'Hello', '<i>Hello</i>', 'html');

            assert.strictEqual(event1.equals(event2), false);
        });

        it('should return false for different format types', () => {
            const event1 = new ClipboardEvent('text', 'Hello', 'content', 'html');
            const event2 = new ClipboardEvent('text', 'Hello', 'content', 'rtf');

            assert.strictEqual(event1.equals(event2), false);
        });

        it('should ignore timestamp in comparison', () => {
            const event1 = new ClipboardEvent('text', 'Hello');
            // Wait a bit to ensure different timestamp
            const event2 = new ClipboardEvent('text', 'Hello');

            assert.strictEqual(event1.equals(event2), true);
        });

        it('should handle null other', () => {
            const event = new ClipboardEvent('text', 'Hello');

            assert.strictEqual(!!event.equals(null), false);
        });

        it('should handle undefined other', () => {
            const event = new ClipboardEvent('text', 'Hello');

            assert.strictEqual(!!event.equals(undefined), false);
        });
    });

    describe('toJSON', () => {
        it('should serialize basic event', () => {
            const event = new ClipboardEvent('text', 'Hello World');
            const json = event.toJSON();

            assert.deepStrictEqual(json, {
                type: 'text',
                content: 'Hello World'
            });
        });

        it('should serialize event with formatted content', () => {
            const event = new ClipboardEvent(
                'text',
                'Hello',
                '<b>Hello</b>',
                'html'
            );
            const json = event.toJSON();

            assert.deepStrictEqual(json, {
                type: 'text',
                content: 'Hello',
                formatted_content: '<b>Hello</b>',
                format_type: 'html'
            });
        });

        it('should serialize file event', () => {
            const event = new ClipboardEvent('file', 'file:///home/user/test.txt');
            const json = event.toJSON();

            assert.deepStrictEqual(json, {
                type: 'file',
                content: 'file:///home/user/test.txt'
            });
        });

        it('should serialize image event', () => {
            const imageData = JSON.stringify({
                mimeType: 'image/png',
                data: 'base64data'
            });
            const event = new ClipboardEvent('image/screenshot', imageData);
            const json = event.toJSON();

            assert.deepStrictEqual(json, {
                type: 'image/screenshot',
                content: imageData
            });
        });

        it('should not include formatted fields when null', () => {
            const event = new ClipboardEvent('text', 'Hello', null, null);
            const json = event.toJSON();

            assert.strictEqual(json.formatted_content, undefined);
            assert.strictEqual(json.format_type, undefined);
        });

        it('should not include timestamp in JSON', () => {
            const event = new ClipboardEvent('text', 'Hello');
            const json = event.toJSON();

            assert.strictEqual(json.timestamp, undefined);
        });
    });
});
