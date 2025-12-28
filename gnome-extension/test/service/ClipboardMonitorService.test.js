import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert';
import { ClipboardEvent } from '../../src/domain/ClipboardEvent.js';
import { FakeClipboardPort } from '../fakes/FakeClipboardPort.js';
import { FakeNotificationPort } from '../fakes/FakeNotificationPort.js';

// Testable version of ClipboardMonitorService without GJS dependencies
class TestableClipboardMonitorService {
    constructor(clipboardPort, notificationPort) {
        this.clipboardPort = clipboardPort;
        this.notificationPort = notificationPort;
        this.lastEvent = null;
    }

    async checkAndNotify() {
        const mimeTypes = await this.clipboardPort.getMimeTypes();

        const sendEvent = async (type, data, formattedContent = null, formatType = null) => {
            const event = new ClipboardEvent(type, data, formattedContent, formatType);
            if (this.isDuplicate(event)) {
                return;
            }
            this.lastEvent = event;
            await this.notificationPort.send(event);
        };

        // 1. Check for file copy
        if (mimeTypes.includes('text/uri-list')) {
            const uriList = await this.clipboardPort.getText();
            if (uriList) {
                const uris = uriList.split('\n').map(u => u.trim()).filter(u => u);
                const allFiles = uris.every(u => u.startsWith('file://'));

                if (allFiles && uris.length > 0) {
                    await sendEvent('file', uriList);
                    return;
                }
            }
        }

        // 2. Check for image (if not a file copy)
        const image = await this.clipboardPort.getImage();
        if (image) {
            let imageType = 'image/generic';
            if (mimeTypes.includes('text/html')) {
                imageType = 'image/web';
            } else if (mimeTypes.includes('image/png') || mimeTypes.includes('image/jpeg')) {
                const hasOtherRelevantMimeTypes = mimeTypes.some(
                    (m) => m.startsWith('text/') || m.includes('html')
                );
                if (!hasOtherRelevantMimeTypes) {
                    imageType = 'image/screenshot';
                }
            }
            await sendEvent(imageType, JSON.stringify(image));
            return;
        }

        // 3. Check for text (if not an image or file)
        const text = await this.clipboardPort.getText();
        if (text) {
            const trimmedText = text.trim();
            if (trimmedText.startsWith('/') && !trimmedText.includes('\n')) {
                const fileUri = `file://${trimmedText}`;
                await sendEvent('file', fileUri);
                return;
            }

            const formattedText = await this.clipboardPort.getFormattedText();
            if (formattedText) {
                await sendEvent('text', text, formattedText.content, formattedText.formatType);
            } else {
                await sendEvent('text', text);
            }
            return;
        }
    }

    isDuplicate(event) {
        return this.lastEvent && this.lastEvent.equals(event);
    }
}

describe('ClipboardMonitorService', () => {
    let clipboardPort;
    let notificationPort;
    let service;

    beforeEach(() => {
        clipboardPort = new FakeClipboardPort();
        notificationPort = new FakeNotificationPort();
        service = new TestableClipboardMonitorService(clipboardPort, notificationPort);
    });

    describe('text clipboard changes', () => {
        it('should detect plain text change', async () => {
            clipboardPort.setText('Hello World');
            clipboardPort.setMimeTypes(['text/plain']);

            await service.checkAndNotify();

            assert.strictEqual(notificationPort.getEventCount(), 1);
            const event = notificationPort.getLastEvent();
            assert.strictEqual(event.type, 'text');
            assert.strictEqual(event.content, 'Hello World');
            assert.strictEqual(event.formattedContent, null);
        });

        it('should detect formatted text (HTML)', async () => {
            clipboardPort.setText('Hello');
            clipboardPort.setFormattedText('html', '<b>Hello</b>');
            clipboardPort.setMimeTypes(['text/plain', 'text/html']);

            await service.checkAndNotify();

            assert.strictEqual(notificationPort.getEventCount(), 1);
            const event = notificationPort.getLastEvent();
            assert.strictEqual(event.type, 'text');
            assert.strictEqual(event.content, 'Hello');
            assert.strictEqual(event.formattedContent, '<b>Hello</b>');
            assert.strictEqual(event.formatType, 'html');
        });

        it('should detect formatted text (RTF)', async () => {
            clipboardPort.setText('Hello');
            clipboardPort.setFormattedText('rtf', '{\\rtf1 Hello}');
            clipboardPort.setMimeTypes(['text/plain', 'text/rtf']);

            await service.checkAndNotify();

            assert.strictEqual(notificationPort.getEventCount(), 1);
            const event = notificationPort.getLastEvent();
            assert.strictEqual(event.type, 'text');
            assert.strictEqual(event.content, 'Hello');
            assert.strictEqual(event.formattedContent, '{\\rtf1 Hello}');
            assert.strictEqual(event.formatType, 'rtf');
        });

        it('should convert absolute file path to file event', async () => {
            clipboardPort.setText('/home/user/document.txt');
            clipboardPort.setMimeTypes(['text/plain']);

            await service.checkAndNotify();

            assert.strictEqual(notificationPort.getEventCount(), 1);
            const event = notificationPort.getLastEvent();
            assert.strictEqual(event.type, 'file');
            assert.strictEqual(event.content, 'file:///home/user/document.txt');
        });

        it('should not convert multi-line text to file event', async () => {
            clipboardPort.setText('/home/user/file1.txt\n/home/user/file2.txt');
            clipboardPort.setMimeTypes(['text/plain']);

            await service.checkAndNotify();

            const event = notificationPort.getLastEvent();
            assert.strictEqual(event.type, 'text');
            assert.strictEqual(event.content, '/home/user/file1.txt\n/home/user/file2.txt');
        });
    });

    describe('file clipboard changes', () => {
        it('should detect file copy', async () => {
            clipboardPort.setText('file:///home/user/test.txt');
            clipboardPort.setMimeTypes(['text/uri-list']);

            await service.checkAndNotify();

            assert.strictEqual(notificationPort.getEventCount(), 1);
            const event = notificationPort.getLastEvent();
            assert.strictEqual(event.type, 'file');
            assert.strictEqual(event.content, 'file:///home/user/test.txt');
        });

        it('should detect multiple file copy', async () => {
            const files = 'file:///home/user/test1.txt\nfile:///home/user/test2.txt';
            clipboardPort.setText(files);
            clipboardPort.setMimeTypes(['text/uri-list']);

            await service.checkAndNotify();

            assert.strictEqual(notificationPort.getEventCount(), 1);
            const event = notificationPort.getLastEvent();
            assert.strictEqual(event.type, 'file');
            assert.strictEqual(event.content, files);
        });

        it('should not treat non-file URIs as file events', async () => {
            clipboardPort.setText('http://example.com\nhttps://test.com');
            clipboardPort.setMimeTypes(['text/uri-list']);

            await service.checkAndNotify();

            const event = notificationPort.getLastEvent();
            // Should fall through to text handling
            assert.strictEqual(event.type, 'text');
        });
    });

    describe('image clipboard changes', () => {
        it('should detect image/screenshot type', async () => {
            const imageData = 'base64encodeddata';
            clipboardPort.setImage('image/png', imageData);
            clipboardPort.setMimeTypes(['image/png']);

            await service.checkAndNotify();

            assert.strictEqual(notificationPort.getEventCount(), 1);
            const event = notificationPort.getLastEvent();
            assert.strictEqual(event.type, 'image/screenshot');
            const parsedContent = JSON.parse(event.content);
            assert.strictEqual(parsedContent.mimeType, 'image/png');
            assert.strictEqual(parsedContent.data, imageData);
        });

        it('should detect image/web type when HTML is present', async () => {
            const imageData = 'base64encodeddata';
            clipboardPort.setImage('image/png', imageData);
            clipboardPort.setMimeTypes(['image/png', 'text/html']);

            await service.checkAndNotify();

            assert.strictEqual(notificationPort.getEventCount(), 1);
            const event = notificationPort.getLastEvent();
            assert.strictEqual(event.type, 'image/web');
        });

        it('should detect image/generic type for other cases', async () => {
            const imageData = 'base64encodeddata';
            clipboardPort.setImage('image/png', imageData);
            clipboardPort.setMimeTypes(['image/png', 'text/plain']);

            await service.checkAndNotify();

            assert.strictEqual(notificationPort.getEventCount(), 1);
            const event = notificationPort.getLastEvent();
            assert.strictEqual(event.type, 'image/generic');
        });

        it('should handle JPEG images', async () => {
            const imageData = 'base64encodeddata';
            clipboardPort.setImage('image/jpeg', imageData);
            clipboardPort.setMimeTypes(['image/jpeg']);

            await service.checkAndNotify();

            assert.strictEqual(notificationPort.getEventCount(), 1);
            const event = notificationPort.getLastEvent();
            assert.strictEqual(event.type, 'image/screenshot');
        });
    });

    describe('priority handling', () => {
        it('should prioritize file over image', async () => {
            clipboardPort.setText('file:///home/user/image.png');
            clipboardPort.setImage('image/png', 'imagedata');
            clipboardPort.setMimeTypes(['text/uri-list', 'image/png']);

            await service.checkAndNotify();

            const event = notificationPort.getLastEvent();
            assert.strictEqual(event.type, 'file');
        });

        it('should prioritize image over text', async () => {
            clipboardPort.setText('some text');
            clipboardPort.setImage('image/png', 'imagedata');
            // When both text and image are present, it's generic (like from a web page)
            clipboardPort.setMimeTypes(['text/plain', 'image/png']);

            await service.checkAndNotify();

            const event = notificationPort.getLastEvent();
            // With text/plain present, it's considered generic
            assert.strictEqual(event.type, 'image/generic');
        });
    });

    describe('duplicate detection', () => {
        it('should not send duplicate text events', async () => {
            clipboardPort.setText('Hello World');
            clipboardPort.setMimeTypes(['text/plain']);

            await service.checkAndNotify();
            await service.checkAndNotify();
            await service.checkAndNotify();

            assert.strictEqual(notificationPort.getEventCount(), 1);
        });

        it('should send event when content changes', async () => {
            clipboardPort.setText('Hello');
            clipboardPort.setMimeTypes(['text/plain']);
            await service.checkAndNotify();

            clipboardPort.setText('World');
            await service.checkAndNotify();

            assert.strictEqual(notificationPort.getEventCount(), 2);
            assert.strictEqual(notificationPort.sentEvents[0].content, 'Hello');
            assert.strictEqual(notificationPort.sentEvents[1].content, 'World');
        });

        it('should detect duplicate file events', async () => {
            clipboardPort.setText('file:///home/user/test.txt');
            clipboardPort.setMimeTypes(['text/uri-list']);

            await service.checkAndNotify();
            await service.checkAndNotify();

            assert.strictEqual(notificationPort.getEventCount(), 1);
        });

        it('should detect duplicate image events', async () => {
            clipboardPort.setImage('image/png', 'samedata');
            clipboardPort.setMimeTypes(['image/png']);

            await service.checkAndNotify();
            await service.checkAndNotify();

            assert.strictEqual(notificationPort.getEventCount(), 1);
        });

        it('should treat different formatted content as different', async () => {
            clipboardPort.setText('Hello');
            clipboardPort.setFormattedText('html', '<b>Hello</b>');
            clipboardPort.setMimeTypes(['text/plain', 'text/html']);
            await service.checkAndNotify();

            clipboardPort.setFormattedText('html', '<i>Hello</i>');
            await service.checkAndNotify();

            assert.strictEqual(notificationPort.getEventCount(), 2);
        });
    });

    describe('empty clipboard', () => {
        it('should not send event when clipboard is empty', async () => {
            clipboardPort.clear();

            await service.checkAndNotify();

            assert.strictEqual(notificationPort.getEventCount(), 0);
        });

        it('should not send event when text is null', async () => {
            clipboardPort.setText(null);
            clipboardPort.setMimeTypes(['text/plain']);

            await service.checkAndNotify();

            assert.strictEqual(notificationPort.getEventCount(), 0);
        });

        it('should not send event when image is null', async () => {
            clipboardPort.setImage(null, null);
            clipboardPort.setMimeTypes(['image/png']);

            await service.checkAndNotify();

            assert.strictEqual(notificationPort.getEventCount(), 0);
        });
    });

    describe('isDuplicate', () => {
        it('should return true for identical events', async () => {
            clipboardPort.setText('Test');
            clipboardPort.setMimeTypes(['text/plain']);
            await service.checkAndNotify();

            const event = notificationPort.getLastEvent();
            // Create new event with same data
            const duplicateEvent = {
                type: 'text',
                content: 'Test',
                formattedContent: null,
                formatType: null,
                equals: function(other) {
                    return this.type === other.type &&
                           this.content === other.content &&
                           this.formattedContent === other.formattedContent &&
                           this.formatType === other.formatType;
                }
            };

            assert.strictEqual(service.isDuplicate(duplicateEvent), true);
        });

        it('should return false when no last event', () => {
            const event = {
                type: 'text',
                content: 'Test',
                formattedContent: null,
                formatType: null,
                equals: function() { return true; }
            };

            assert.strictEqual(!!service.isDuplicate(event), false);
        });
    });
});
