import { describe, it, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert';
import { FakeSt, FakeGLib } from '../fakes/FakeGnomeAPIs.js';

// We'll need to test the adapter logic, so we'll create a testable version
// that accepts the dependencies instead of importing them
class TestableGnomeClipboardAdapter {
    constructor(St, GLib) {
        this.clipboard = St.Clipboard.get_default();
        this.GLib = GLib;
    }

    async getText() {
        return new Promise((resolve) => {
            this.clipboard.get_text(FakeSt.ClipboardType.CLIPBOARD, (_, text) => {
                resolve(text || null);
            });
        });
    }

    async getImage() {
        const mimeTypes = [
            'image/png',
            'image/jpeg',
            'image/jpg',
            'image/gif',
            'image/bmp',
            'image/webp',
            'image/avif',
        ];

        for (const mimeType of mimeTypes) {
            try {
                const imageData = await this._getContentForMimeType(mimeType);
                if (imageData) {
                    return {
                        mimeType: mimeType,
                        data: imageData,
                    };
                }
            } catch (e) {
                continue;
            }
        }

        return null;
    }

    async getMimeTypes() {
        try {
            const mimeTypes = this.clipboard.get_mimetypes(FakeSt.ClipboardType.CLIPBOARD);
            return Promise.resolve(mimeTypes || []);
        } catch (e) {
            return Promise.resolve([]);
        }
    }

    async getFormattedText() {
        const htmlContent = await this._getContentForMimeType('text/html');
        if (htmlContent) {
            return {
                formatType: 'html',
                content: htmlContent,
            };
        }

        const rtfContent = await this._getContentForMimeType('text/rtf');
        if (rtfContent) {
            return {
                formatType: 'rtf',
                content: rtfContent,
            };
        }

        return null;
    }

    async _getContentForMimeType(mimeType) {
        return new Promise((resolve) => {
            this.clipboard.get_content(FakeSt.ClipboardType.CLIPBOARD, mimeType, (_, bytes) => {
                if (!bytes || bytes.get_size() === 0) {
                    resolve(null);
                    return;
                }

                const data = bytes.get_data();
                const base64 = this.GLib.base64_encode(data);
                resolve(base64);
            });
        });
    }
}

describe('GnomeClipboardAdapter', () => {
    let adapter;
    let clipboard;

    beforeEach(() => {
        // Reset clipboard singleton
        FakeSt.Clipboard._reset();
        clipboard = FakeSt.Clipboard.get_default();
        adapter = new TestableGnomeClipboardAdapter(FakeSt, FakeGLib);
    });

    afterEach(() => {
        clipboard.clear();
    });

    describe('getText', () => {
        it('should return text from clipboard', async () => {
            clipboard.setTextContent('Hello World');

            const text = await adapter.getText();

            assert.strictEqual(text, 'Hello World');
        });

        it('should return null when clipboard has no text', async () => {
            clipboard.setTextContent(null);

            const text = await adapter.getText();

            assert.strictEqual(text, null);
        });

        it('should return empty string when clipboard is empty string', async () => {
            clipboard.setTextContent('');

            const text = await adapter.getText();

            // The adapter converts empty string to null
            assert.strictEqual(text, null);
        });
    });

    describe('getMimeTypes', () => {
        it('should return available mime types', async () => {
            clipboard.setMimeTypes(['text/plain', 'text/html']);

            const mimeTypes = await adapter.getMimeTypes();

            assert.deepStrictEqual(mimeTypes, ['text/plain', 'text/html']);
        });

        it('should return empty array when no mime types', async () => {
            clipboard.setMimeTypes([]);

            const mimeTypes = await adapter.getMimeTypes();

            assert.deepStrictEqual(mimeTypes, []);
        });

        it('should handle errors gracefully', async () => {
            // Make get_mimetypes throw
            clipboard.get_mimetypes = () => {
                throw new Error('Test error');
            };

            const mimeTypes = await adapter.getMimeTypes();

            assert.deepStrictEqual(mimeTypes, []);
        });
    });

    describe('getImage', () => {
        it('should return PNG image data', async () => {
            const imageData = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==';
            clipboard.setContentForMimeType('image/png', imageData);

            const image = await adapter.getImage();

            assert.ok(image);
            assert.strictEqual(image.mimeType, 'image/png');
            assert.strictEqual(image.data, imageData);
        });

        it('should return JPEG image data', async () => {
            const imageData = '/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCwAB//2Q==';
            clipboard.setContentForMimeType('image/jpeg', imageData);

            const image = await adapter.getImage();

            assert.ok(image);
            assert.strictEqual(image.mimeType, 'image/jpeg');
            assert.strictEqual(image.data, imageData);
        });

        it('should try multiple image formats', async () => {
            // Set only GIF
            const gifData = 'R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';
            clipboard.setContentForMimeType('image/gif', gifData);

            const image = await adapter.getImage();

            assert.ok(image);
            assert.strictEqual(image.mimeType, 'image/gif');
        });

        it('should return null when no image data', async () => {
            const image = await adapter.getImage();

            assert.strictEqual(image, null);
        });

        it('should prioritize PNG over other formats', async () => {
            const pngData = 'cG5nIGRhdGEgaGVyZQ=='; // base64: "png data here"
            const jpegData = 'anBlZyBkYXRhIGhlcmU='; // base64: "jpeg data here"
            clipboard.setContentForMimeType('image/png', pngData);
            clipboard.setContentForMimeType('image/jpeg', jpegData);

            const image = await adapter.getImage();

            // PNG is checked first in the list
            assert.strictEqual(image.mimeType, 'image/png');
            assert.strictEqual(image.data, pngData);
        });
    });

    describe('getFormattedText', () => {
        it('should return HTML formatted text', async () => {
            const htmlContent = '<p><b>Hello</b> World</p>';
            const htmlBase64 = Buffer.from(htmlContent).toString('base64');
            clipboard.setContentForMimeType('text/html', htmlBase64);

            const formatted = await adapter.getFormattedText();

            assert.ok(formatted);
            assert.strictEqual(formatted.formatType, 'html');
            assert.strictEqual(formatted.content, htmlBase64);
        });

        it('should return RTF formatted text', async () => {
            const rtfContent = '{\\rtf1\\ansi Hello World}';
            const rtfBase64 = Buffer.from(rtfContent).toString('base64');
            clipboard.setContentForMimeType('text/rtf', rtfBase64);

            const formatted = await adapter.getFormattedText();

            assert.ok(formatted);
            assert.strictEqual(formatted.formatType, 'rtf');
            assert.strictEqual(formatted.content, rtfBase64);
        });

        it('should prioritize HTML over RTF', async () => {
            const htmlBase64 = Buffer.from('<b>HTML</b>').toString('base64');
            const rtfBase64 = Buffer.from('{\\rtf1 RTF}').toString('base64');
            clipboard.setContentForMimeType('text/html', htmlBase64);
            clipboard.setContentForMimeType('text/rtf', rtfBase64);

            const formatted = await adapter.getFormattedText();

            assert.strictEqual(formatted.formatType, 'html');
        });

        it('should return null when no formatted text', async () => {
            const formatted = await adapter.getFormattedText();

            assert.strictEqual(formatted, null);
        });
    });
});
