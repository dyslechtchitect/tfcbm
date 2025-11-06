import { ClipboardEvent } from './domain/ClipboardEvent.js';

export class ClipboardMonitorService {
    constructor(clipboardPort, notificationPort) {
        this.clipboardPort = clipboardPort;
        this.notificationPort = notificationPort;
        this.lastEvent = null;
    }

    async checkAndNotify() {
        // Check for text first (priority)
        const text = await this.clipboardPort.getText();

        if (text) {
            const event = new ClipboardEvent('text', text);

            if (this.isDuplicate(event)) {
                return;
            }

            this.lastEvent = event;
            await this.notificationPort.send(event);
            return;
        }

        // If no text, check for images
        const image = await this.clipboardPort.getImage();

        if (image) {
            const event = new ClipboardEvent('image', JSON.stringify(image));

            if (this.isDuplicate(event)) {
                return;
            }

            this.lastEvent = event;
            await this.notificationPort.send(event);
        }
    }

    isDuplicate(event) {
        return this.lastEvent && this.lastEvent.equals(event);
    }
}
