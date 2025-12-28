/**
 * Fake GNOME APIs for testing adapters without requiring actual GNOME Shell
 */

export class FakeClipboard {
    constructor() {
        this._textContent = null;
        this._mimeTypes = [];
        this._contentByMimeType = new Map();
    }

    // Test helper methods
    setTextContent(text) {
        this._textContent = text;
    }

    setMimeTypes(mimeTypes) {
        this._mimeTypes = [...mimeTypes];
    }

    setContentForMimeType(mimeType, base64Data) {
        this._contentByMimeType.set(mimeType, base64Data);
    }

    clear() {
        this._textContent = null;
        this._mimeTypes = [];
        this._contentByMimeType.clear();
    }

    // St.Clipboard API
    get_text(clipboardType, callback) {
        // Simulate async callback
        setImmediate(() => callback(this, this._textContent));
    }

    get_mimetypes(clipboardType) {
        return this._mimeTypes;
    }

    get_content(clipboardType, mimeType, callback) {
        const base64Data = this._contentByMimeType.get(mimeType);

        if (!base64Data) {
            setImmediate(() => callback(this, null));
            return;
        }

        // Convert base64 back to bytes for the fake
        const bytes = {
            get_size: () => base64Data.length,
            get_data: () => {
                // For testing, we'll just return a simple buffer
                // In real GJS this would be GBytes
                return Buffer.from(base64Data, 'base64');
            }
        };

        setImmediate(() => callback(this, bytes));
    }
}

export class FakeGLib {
    static base64_encode(data) {
        if (Buffer.isBuffer(data)) {
            return data.toString('base64');
        }
        // For Uint8Array or array-like
        return Buffer.from(data).toString('base64');
    }

    static PRIORITY_DEFAULT = 0;
    static SOURCE_CONTINUE = true;
    static SOURCE_REMOVE = false;

    static _timeoutIdCounter = 1;
    static _timeouts = new Map();

    static timeout_add(priority, intervalMs, callback) {
        const id = this._timeoutIdCounter++;
        const interval = setInterval(() => {
            try {
                const result = callback();
                if (result !== this.SOURCE_CONTINUE) {
                    clearInterval(interval);
                    this._timeouts.delete(id);
                }
            } catch (e) {
                // In real GLib, errors in callbacks are logged but don't stop the timer
                // Continue running on error
            }
        }, intervalMs);
        this._timeouts.set(id, interval);
        return id;
    }

    static Source = {
        remove(timeoutId) {
            const interval = FakeGLib._timeouts.get(timeoutId);
            if (interval) {
                clearInterval(interval);
                FakeGLib._timeouts.delete(timeoutId);
                return true;
            }
            return false;
        }
    };

    // Cleanup helper for tests
    static _cleanup() {
        for (const interval of this._timeouts.values()) {
            clearInterval(interval);
        }
        this._timeouts.clear();
    }
}

export class FakeDBus {
    constructor() {
        this._calls = [];
        this._shouldSucceed = true;
    }

    // Test helpers
    setShouldSucceed(shouldSucceed) {
        this._shouldSucceed = shouldSucceed;
    }

    getCalls() {
        return this._calls;
    }

    getLastCall() {
        return this._calls[this._calls.length - 1] || null;
    }

    clear() {
        this._calls = [];
    }

    // Gio.DBus.session API
    call(busName, objectPath, interfaceName, methodName, parameters, replyType, flags, timeout, cancellable, callback) {
        // Record the call
        const callRecord = {
            busName,
            objectPath,
            interfaceName,
            methodName,
            parameters: parameters ? this._unpackVariant(parameters) : null,
            timeout
        };
        this._calls.push(callRecord);

        // Simulate async callback
        setImmediate(() => {
            if (this._shouldSucceed) {
                callback(this, {
                    call_finish: () => null // Success
                });
            } else {
                callback(this, {
                    call_finish: () => {
                        throw new Error('DBus call failed');
                    }
                });
            }
        });
    }

    _unpackVariant(variant) {
        // For testing, we'll assume a simple structure
        // In real code, variant would be a GLib.Variant
        if (variant && variant.signature === '(s)' && variant.value) {
            return variant.value;
        }
        return variant;
    }
}

// Fake GLib.Variant for DBus calls
export class FakeVariant {
    constructor(signature, value) {
        this.signature = signature;
        this.value = value;
    }
}

// Export a structure that mimics the GNOME imports
export const FakeSt = {
    Clipboard: {
        _instance: null,
        get_default() {
            if (!this._instance) {
                this._instance = new FakeClipboard();
            }
            return this._instance;
        },
        _reset() {
            this._instance = null;
        }
    },
    ClipboardType: {
        CLIPBOARD: 0,
        PRIMARY: 1
    }
};

export const FakeGio = {
    DBus: {
        session: new FakeDBus()
    },
    DBusCallFlags: {
        NONE: 0
    }
};
