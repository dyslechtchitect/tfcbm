import { ClipboardEvent } from './domain/ClipboardEvent.js';

export class ClipboardMonitorService {
    constructor(clipboardPort, notificationPort) {
        this.clipboardPort = clipboardPort;
        this.notificationPort = notificationPort;
        this.lastEvent = null;
    }

    async checkAndNotify() {
        log('[TFCBM] checkAndNotify called');
        const mimeTypes = await this.clipboardPort.getMimeTypes();
        log(`[TFCBM] Mime types: ${mimeTypes.join(', ')}`);

        const sendEvent = async (type, data) => {
            const event = new ClipboardEvent(type, data);
            if (this.isDuplicate(event)) {
                return;
            }
            this.lastEvent = event;
            await this.notificationPort.send(event);
        };

        // 1. Check for image
        const image = await this.clipboardPort.getImage();
        if (image) {
            let imageType = 'image/generic';
            if (mimeTypes.includes('text/uri-list')) {
                imageType = 'image/file';
            } else if (mimeTypes.includes('text/html')) {
                imageType = 'image/web';
            } else if (mimeTypes.includes('image/png') || mimeTypes.includes('image/jpeg')) {
                const hasOtherRelevantMimeTypes = mimeTypes.some(m =>
                    m.startsWith('text/') || m.includes('uri-list') || m.includes('html')
                );
                if (!hasOtherRelevantMimeTypes) {
                    imageType = 'image/screenshot';
                }
            }
            await sendEvent(imageType, JSON.stringify(image));
            return;
        }

        // 2. Check for file copy (if not an image)
        if (mimeTypes.includes('text/uri-list')) {
            const uriList = await this.clipboardPort.getText();
            if (uriList) {
                const uri = uriList.split('\n')[0].trim();
                if (uri.startsWith('file://')) {
                    await sendEvent('file', uri);
                    return;
                }
            }
        }

        // 3. Check for text
        const text = await this.clipboardPort.getText();
        if (text) {
            await sendEvent('text', text);
            return;
        }
    }

    isDuplicate(event) {
        return this.lastEvent && this.lastEvent.equals(event);
    }
}
