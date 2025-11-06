import { ClipboardMonitorService } from '../../src/ClipboardMonitorService.js';
import { ClipboardPort } from '../../src/domain/ClipboardPort.js';
import { NotificationPort } from '../../src/domain/NotificationPort.js';

class FakeClipboard extends ClipboardPort {
    constructor(text = null, image = null) {
        super();
        this.text = text;
        this.image = image;
    }

    async getText() {
        return this.text;
    }

    async getImage() {
        return this.image;
    }
}

class SpyNotification extends NotificationPort {
    constructor() {
        super();
        this.events = [];
    }

    async send(event) {
        this.events.push(event);
    }
}

describe('ClipboardMonitorService', () => {
    test('notifies when clipboard has new text', async () => {
        const clipboard = new FakeClipboard('hello world');
        const notification = new SpyNotification();
        const service = new ClipboardMonitorService(clipboard, notification);

        await service.checkAndNotify();

        expect(notification.events).toHaveLength(1);
        expect(notification.events[0].type).toBe('text');
        expect(notification.events[0].content).toBe('hello world');
    });

    test('does not notify when clipboard is empty', async () => {
        const clipboard = new FakeClipboard(null);
        const notification = new SpyNotification();
        const service = new ClipboardMonitorService(clipboard, notification);

        await service.checkAndNotify();

        expect(notification.events).toHaveLength(0);
    });

    test('does not notify for duplicate content', async () => {
        const clipboard = new FakeClipboard('same text');
        const notification = new SpyNotification();
        const service = new ClipboardMonitorService(clipboard, notification);

        await service.checkAndNotify();
        await service.checkAndNotify();

        expect(notification.events).toHaveLength(1);
    });

    test('notifies when clipboard content changes', async () => {
        const clipboard = new FakeClipboard('first');
        const notification = new SpyNotification();
        const service = new ClipboardMonitorService(clipboard, notification);

        await service.checkAndNotify();

        clipboard.text = 'second';
        await service.checkAndNotify();

        expect(notification.events).toHaveLength(2);
        expect(notification.events[0].content).toBe('first');
        expect(notification.events[1].content).toBe('second');
    });

    test('notifies when clipboard has new image', async () => {
        const imageData = { mimeType: 'image/png', data: 'base64data' };
        const clipboard = new FakeClipboard(null, imageData);
        const notification = new SpyNotification();
        const service = new ClipboardMonitorService(clipboard, notification);

        await service.checkAndNotify();

        expect(notification.events).toHaveLength(1);
        expect(notification.events[0].type).toBe('image');
        expect(notification.events[0].content).toBe(JSON.stringify(imageData));
    });

    test('does not notify for duplicate images', async () => {
        const imageData = { mimeType: 'image/png', data: 'base64data' };
        const clipboard = new FakeClipboard(null, imageData);
        const notification = new SpyNotification();
        const service = new ClipboardMonitorService(clipboard, notification);

        await service.checkAndNotify();
        await service.checkAndNotify();

        expect(notification.events).toHaveLength(1);
    });

    test('notifies when image content changes', async () => {
        const imageData1 = { mimeType: 'image/png', data: 'base64data1' };
        const imageData2 = { mimeType: 'image/png', data: 'base64data2' };
        const clipboard = new FakeClipboard(null, imageData1);
        const notification = new SpyNotification();
        const service = new ClipboardMonitorService(clipboard, notification);

        await service.checkAndNotify();

        clipboard.image = imageData2;
        await service.checkAndNotify();

        expect(notification.events).toHaveLength(2);
        expect(notification.events[0].content).toBe(JSON.stringify(imageData1));
        expect(notification.events[1].content).toBe(JSON.stringify(imageData2));
    });

    test('text takes priority over image', async () => {
        const imageData = { mimeType: 'image/png', data: 'base64data' };
        const clipboard = new FakeClipboard('some text', imageData);
        const notification = new SpyNotification();
        const service = new ClipboardMonitorService(clipboard, notification);

        await service.checkAndNotify();

        expect(notification.events).toHaveLength(1);
        expect(notification.events[0].type).toBe('text');
        expect(notification.events[0].content).toBe('some text');
    });

    test('notifies when switching from text to image', async () => {
        const imageData = { mimeType: 'image/png', data: 'base64data' };
        const clipboard = new FakeClipboard('some text', null);
        const notification = new SpyNotification();
        const service = new ClipboardMonitorService(clipboard, notification);

        await service.checkAndNotify();

        clipboard.text = null;
        clipboard.image = imageData;
        await service.checkAndNotify();

        expect(notification.events).toHaveLength(2);
        expect(notification.events[0].type).toBe('text');
        expect(notification.events[1].type).toBe('image');
    });
});
