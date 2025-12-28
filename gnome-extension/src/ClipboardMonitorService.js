import { ClipboardEvent } from './domain/ClipboardEvent.js';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

export class ClipboardMonitorService {
    constructor(clipboardPort, notificationPort) {
        this.clipboardPort = clipboardPort;
        this.notificationPort = notificationPort;
        this.lastEvent = null;
    }

    async checkAndNotify() {
        const mimeTypes = await this.clipboardPort.getMimeTypes();

        // Log mime types for debugging
        log(`[TFCBM] Available mime types: ${JSON.stringify(mimeTypes)}`);

        const sendEvent = async (type, data, formattedContent = null, formatType = null) => {
            const event = new ClipboardEvent(type, data, formattedContent, formatType);
            if (this.isDuplicate(event)) {
                return;
            }
            // Log clipboard event (type and size only, no content)
            const size = typeof data === 'string' ? data.length : 0;
            const formatInfo = formatType ? ` [${formatType}]` : '';
            log(`[TFCBM] Clipboard event: ${type} (${size} bytes)${formatInfo}`);
            this.lastEvent = event;
            await this.notificationPort.send(event);
        };

        // 1. Check for file copy
        if (mimeTypes.includes('text/uri-list')) {
            const uriList = await this.clipboardPort.getText();
            if (uriList) {
                // Check if all URIs are file URIs
                const uris = uriList.split('\n').map(u => u.trim()).filter(u => u);
                const allFiles = uris.every(u => u.startsWith('file://'));

                if (allFiles && uris.length > 0) {
                    log(`[TFCBM] Detected file copy event with ${uris.length} files.`);
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
            // Check if text looks like a file path
            const trimmedText = text.trim();
            if (trimmedText.startsWith('/') && !trimmedText.includes('\n')) {
                // Looks like an absolute file path - treat as file
                // Convert to file:// URI
                const fileUri = `file://${trimmedText}`;
                log(`[TFCBM] Detected file path in text, converting: ${fileUri}`);
                await sendEvent('file', fileUri);
                return;
            }

            // Check for formatted text (HTML/RTF)
            const formattedText = await this.clipboardPort.getFormattedText();
            if (formattedText) {
                log(
                    `[TFCBM] Detected formatted text: ${formattedText.formatType}, size: ${formattedText.content.length}`
                );
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

    async _readImageFile(filePath) {
        try {
            log(`[TFCBM] Reading image file: ${filePath}`);
            const file = Gio.File.new_for_path(filePath);

            // Read file contents
            const [success, contents] = file.load_contents(null);
            if (!success || !contents) {
                log(`[TFCBM] Failed to read file: ${filePath}`);
                return null;
            }

            // Convert to base64
            const base64 = GLib.base64_encode(contents);

            // Determine mime type from file extension
            const extension = filePath.toLowerCase().split('.').pop();
            const mimeTypeMap = {
                png: 'image/png',
                jpg: 'image/jpeg',
                jpeg: 'image/jpeg',
                gif: 'image/gif',
                bmp: 'image/bmp',
                webp: 'image/webp',
                avif: 'image/avif',
            };
            const mimeType = mimeTypeMap[extension] || 'image/png';

            log(
                `[TFCBM] Successfully read image file: ${filePath}, size: ${contents.length} bytes, mime: ${mimeType}`
            );

            return {
                mimeType: mimeType,
                data: base64,
            };
        } catch (e) {
            log(`[TFCBM] Error reading image file: ${e}`);
            return null;
        }
    }
}
