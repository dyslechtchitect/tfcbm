import { ClipboardPort } from '../../src/domain/ClipboardPort.js';

/**
 * Fake clipboard port for testing.
 * Allows tests to control what clipboard data is returned.
 */
export class FakeClipboardPort extends ClipboardPort {
    constructor() {
        super();
        this._text = null;
        this._image = null;
        this._mimeTypes = [];
        this._formattedText = null;
    }

    // Test helpers to set clipboard state
    setText(text) {
        this._text = text;
        if (text) {
            if (!this._mimeTypes.includes('text/plain')) {
                this._mimeTypes.push('text/plain');
            }
        }
    }

    setImage(mimeType, data) {
        if (mimeType === null || data === null) {
            this._image = null;
            return;
        }
        this._image = { mimeType, data };
        if (!this._mimeTypes.includes(mimeType)) {
            this._mimeTypes.push(mimeType);
        }
    }

    setMimeTypes(mimeTypes) {
        this._mimeTypes = [...mimeTypes];
    }

    setFormattedText(formatType, content) {
        this._formattedText = { formatType, content };
        const mimeType = formatType === 'html' ? 'text/html' : 'text/rtf';
        if (!this._mimeTypes.includes(mimeType)) {
            this._mimeTypes.push(mimeType);
        }
    }

    clear() {
        this._text = null;
        this._image = null;
        this._mimeTypes = [];
        this._formattedText = null;
    }

    // Port implementation
    async getText() {
        return this._text;
    }

    async getImage() {
        return this._image;
    }

    async getMimeTypes() {
        return this._mimeTypes;
    }

    async getFormattedText() {
        return this._formattedText;
    }
}
