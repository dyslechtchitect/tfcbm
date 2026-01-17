import St from 'gi://St';
import GLib from 'gi://GLib';
import { ClipboardPort } from '../domain/ClipboardPort.js';

export class GnomeClipboardAdapter extends ClipboardPort {
    constructor() {
        super();
        this.clipboard = St.Clipboard.get_default();
    }

    async getText() {
        return new Promise((resolve) => {
            this.clipboard.get_text(St.ClipboardType.CLIPBOARD, (_, text) => {
                resolve(text || null);
            });
        });
    }

    async getImage() {
        // Try common image mime types
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
                    log(`[TFCBM] Image found: ${mimeType}`);
                    return {
                        mimeType: mimeType,
                        data: imageData,
                    };
                }
            } catch (e) {
                // Try next mime type
                continue;
            }
        }

        return null;
    }

    async getMimeTypes() {
        try {
            const mimeTypes = this.clipboard.get_mimetypes(St.ClipboardType.CLIPBOARD);
            return Promise.resolve(mimeTypes || []);
        } catch (e) {
            log(`[TFCBM] Error calling get_mimetypes with clipboard type: ${e}`);
            return Promise.resolve([]);
        }
    }

    async getFormattedText() {
        // Try to get HTML formatted text first, then RTF
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
            this.clipboard.get_content(St.ClipboardType.CLIPBOARD, mimeType, (_, bytes) => {
                if (!bytes || bytes.get_size() === 0) {
                    resolve(null);
                    return;
                }

                // Convert bytes to base64
                const data = bytes.get_data();
                const base64 = GLib.base64_encode(data);
                log(
                    `[TFCBM] Got content for ${mimeType}, size: ${data.length} bytes`
                );
                resolve(base64);
            });
        });
    }
}
