import { NotificationPort } from '../../src/domain/NotificationPort.js';

/**
 * Fake notification port for testing.
 * Records all events sent so tests can verify behavior.
 */
export class FakeNotificationPort extends NotificationPort {
    constructor() {
        super();
        this.sentEvents = [];
        this._shouldFail = false;
    }

    async send(event) {
        if (this._shouldFail) {
            return false;
        }

        // Store a copy of the event data (not the object itself)
        this.sentEvents.push({
            type: event.type,
            content: event.content,
            formattedContent: event.formattedContent,
            formatType: event.formatType,
            timestamp: event.timestamp
        });

        return true;
    }

    // Test helpers
    setShouldFail(shouldFail) {
        this._shouldFail = shouldFail;
    }

    getLastEvent() {
        return this.sentEvents[this.sentEvents.length - 1] || null;
    }

    getEventCount() {
        return this.sentEvents.length;
    }

    clear() {
        this.sentEvents = [];
    }

    wasEventSent(predicate) {
        return this.sentEvents.some(predicate);
    }
}
