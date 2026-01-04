/**
 * IPC Client for GNOME Shell Extension
 *
 * Connects to TFCBM backend via UNIX domain socket
 * Sends requests and receives responses/broadcasts
 *
 * Architecture: Adapter pattern - implements communication with backend IPC service
 */

import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

export class IPCClient {
    constructor() {
        this._connection = null;
        this._inputStream = null;
        this._dataInputStream = null;
        this._outputStream = null;
        this._messageHandlers = new Map();
        this._isConnected = false;
        this._socketPath = this._getSocketPath();
        this._readCancellable = null;
    }

    /**
     * Get UNIX socket path from XDG_RUNTIME_DIR
     * @returns {string} Socket path
     */
    _getSocketPath() {
        const runtimeDir = GLib.getenv('XDG_RUNTIME_DIR') || '/tmp';
        return `${runtimeDir}/tfcbm/ipc.sock`;
    }

    /**
     * Connect to backend IPC socket
     * @returns {Promise<boolean>} Success status
     */
    async connect() {
        if (this._isConnected) {
            log('[TFCBM IPC] Already connected');
            return true;
        }

        try {
            log(`[TFCBM IPC] Attempting to connect to: ${this._socketPath}`);

            // Create socket address
            const socketAddress = Gio.UnixSocketAddress.new(this._socketPath);

            // Create socket client
            const client = new Gio.SocketClient();

            // Connect to socket (async)
            this._connection = await new Promise((resolve, reject) => {
                client.connect_async(
                    socketAddress,
                    null, // cancellable
                    (source, result) => {
                        try {
                            const connection = client.connect_finish(result);
                            resolve(connection);
                        } catch (e) {
                            reject(e);
                        }
                    }
                );
            });

            this._inputStream = this._connection.get_input_stream();
            this._dataInputStream = new Gio.DataInputStream({
                base_stream: this._inputStream
            });
            this._outputStream = this._connection.get_output_stream();
            this._isConnected = true;
            this._readCancellable = new Gio.Cancellable();

            log('[TFCBM IPC] Connected to backend');

            // Start reading messages
            this._startReading();

            return true;

        } catch (e) {
            logError(e, '[TFCBM IPC] Failed to connect');
            this._isConnected = false;
            return false;
        }
    }

    /**
     * Start reading messages from socket in a loop
     */
    _startReading() {
        this._readNextMessage();
    }

    /**
     * Read next message from socket (async recursive)
     */
    _readNextMessage() {
        if (!this._isConnected || !this._inputStream) {
            return;
        }

        // Read length prefix (terminated by newline)
        this._readLine((lengthLine) => {
            if (!lengthLine) {
                // Connection closed
                this._handleDisconnect();
                return;
            }

            try {
                const messageLength = parseInt(lengthLine.trim());

                // Read message of exact length
                this._readExact(messageLength, (messageBytes) => {
                    if (!messageBytes) {
                        this._handleDisconnect();
                        return;
                    }

                    try {
                        // Parse JSON message
                        const messageStr = new TextDecoder().decode(messageBytes).trim();
                        const message = JSON.parse(messageStr);

                        // Handle message
                        this._handleMessage(message);

                    } catch (e) {
                        logError(e, '[TFCBM IPC] Failed to parse message');
                    }

                    // Read next message
                    this._readNextMessage();
                });

            } catch (e) {
                logError(e, '[TFCBM IPC] Failed to parse length');
                this._handleDisconnect();
            }
        });
    }

    /**
     * Read a line from input stream (until \n)
     * @param {Function} callback Called with line string
     */
    _readLine(callback) {
        this._dataInputStream.read_line_async(
            GLib.PRIORITY_DEFAULT,
            this._readCancellable,
            (source, result) => {
                try {
                    const [line, length] = this._dataInputStream.read_line_finish_utf8(result);
                    callback(line);
                } catch (e) {
                    if (!e.matches(Gio.IOErrorEnum, Gio.IOErrorEnum.CANCELLED)) {
                        logError(e, '[TFCBM IPC] Error reading line');
                    }
                    callback(null);
                }
            }
        );
    }

    /**
     * Read exact number of bytes from stream
     * @param {number} length Number of bytes to read
     * @param {Function} callback Called with Uint8Array
     */
    _readExact(length, callback) {
        this._dataInputStream.read_bytes_async(
            length,
            GLib.PRIORITY_DEFAULT,
            this._readCancellable,
            (source, result) => {
                try {
                    const bytes = this._dataInputStream.read_bytes_finish(result);
                    if (bytes.get_size() === 0) {
                        callback(null);
                        return;
                    }
                    callback(bytes.get_data());
                } catch (e) {
                    if (!e.matches(Gio.IOErrorEnum, Gio.IOErrorEnum.CANCELLED)) {
                        logError(e, '[TFCBM IPC] Error reading bytes');
                    }
                    callback(null);
                }
            }
        );
    }

    /**
     * Handle incoming message from backend
     * @param {Object} message Parsed JSON message
     */
    _handleMessage(message) {
        const messageType = message.type || message.action;

        log(`[TFCBM IPC] Received message: ${messageType}`);

        // Call registered handlers
        const handlers = this._messageHandlers.get(messageType) || [];
        handlers.forEach(handler => {
            try {
                handler(message);
            } catch (e) {
                logError(e, `[TFCBM IPC] Error in message handler for ${messageType}`);
            }
        });
    }

    /**
     * Handle disconnect
     */
    _handleDisconnect() {
        log('[TFCBM IPC] Disconnected from backend');
        this._isConnected = false;

        // Call disconnect handlers
        const handlers = this._messageHandlers.get('disconnect') || [];
        handlers.forEach(handler => handler());
    }

    /**
     * Send request to backend
     * @param {Object} request Request object
     * @returns {Promise<boolean>} Success status
     */
    async send(request) {
        if (!this._isConnected || !this._outputStream) {
            logError(new Error('Not connected'), '[TFCBM IPC] Cannot send');
            return false;
        }

        try {
            const jsonStr = JSON.stringify(request);
            const messageBytes = new TextEncoder().encode(jsonStr + '\n');
            const lengthPrefix = new TextEncoder().encode(`${messageBytes.length}\n`);

            // Write length prefix
            await this._writeBytes(lengthPrefix);

            // Write message
            await this._writeBytes(messageBytes);

            log(`[TFCBM IPC] Sent: ${request.action}`);
            return true;

        } catch (e) {
            logError(e, '[TFCBM IPC] Failed to send message');
            return false;
        }
    }

    /**
     * Write bytes to output stream
     * @param {Uint8Array} bytes Bytes to write
     * @returns {Promise<void>}
     */
    async _writeBytes(bytes) {
        return new Promise((resolve, reject) => {
            this._outputStream.write_bytes_async(
                new GLib.Bytes(bytes),
                GLib.PRIORITY_DEFAULT,
                null, // cancellable
                (source, result) => {
                    try {
                        this._outputStream.write_bytes_finish(result);
                        resolve();
                    } catch (e) {
                        reject(e);
                    }
                }
            );
        });
    }

    /**
     * Register handler for message type
     * @param {string} messageType Type of message (e.g., 'history', 'new_item')
     * @param {Function} handler Handler function
     */
    on(messageType, handler) {
        if (!this._messageHandlers.has(messageType)) {
            this._messageHandlers.set(messageType, []);
        }
        this._messageHandlers.get(messageType).push(handler);
    }

    /**
     * Unregister handler for message type
     * @param {string} messageType Type of message
     * @param {Function} handler Handler function to remove
     */
    off(messageType, handler) {
        const handlers = this._messageHandlers.get(messageType) || [];
        const index = handlers.indexOf(handler);
        if (index > -1) {
            handlers.splice(index, 1);
        }
    }

    /**
     * Request clipboard history from backend
     * @param {number} limit Maximum items to fetch
     * @param {number} offset Pagination offset
     * @returns {Promise<boolean>} Success status
     */
    async getHistory(limit = 20, offset = 0) {
        return this.send({
            action: 'get_history',
            limit,
            offset
        });
    }

    /**
     * Get all settings from backend
     * @returns {Promise<boolean>} Success status
     */
    async getSettings() {
        return this.send({
            action: 'get_settings'
        });
    }

    /**
     * Update settings on backend
     * @param {Object} settings Settings to update (partial update supported)
     * @returns {Promise<boolean>} Success status
     */
    async updateSettings(settings) {
        return this.send({
            action: 'update_settings',
            settings
        });
    }

    /**
     * Disconnect from backend
     */
    disconnect() {
        if (this._readCancellable) {
            this._readCancellable.cancel();
            this._readCancellable = null;
        }

        if (this._connection) {
            try {
                this._connection.close(null);
            } catch (e) {
                logError(e, '[TFCBM IPC] Error closing connection');
            }
            this._connection = null;
        }

        this._inputStream = null;
        this._dataInputStream = null;
        this._outputStream = null;
        this._isConnected = false;

        log('[TFCBM IPC] Disconnected');
    }

    /**
     * Check if connected to backend
     * @returns {boolean} Connection status
     */
    isConnected() {
        return this._isConnected;
    }
}
