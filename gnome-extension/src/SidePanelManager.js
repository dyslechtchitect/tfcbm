/**
 * Side Panel Manager
 *
 * Orchestrates IPC client and side panel widget
 * Manages panel lifecycle, data fetching, and user interactions
 *
 * Architecture: Service pattern - coordinates adapters and manages state
 */

import St from 'gi://St';
import { IPCClient } from './adapters/IPCClient.js';
import { GnomeSidePanel } from './adapters/GnomeSidePanel.js';

export class SidePanelManager {
    constructor(alignment = 'right') {
        this._alignment = alignment;
        this._ipcClient = null;
        this._panel = null;
        this._clipboard = St.Clipboard.get_default();
        this._isInitialized = false;
    }

    /**
     * Initialize manager - connect to backend and create panel
     * @returns {Promise<boolean>} Success status
     */
    async initialize() {
        if (this._isInitialized) {
            log('[TFCBM Manager] Already initialized');
            return true;
        }

        try {
            // Create IPC client
            this._ipcClient = new IPCClient();

            // Connect to backend
            const connected = await this._ipcClient.connect();
            if (!connected) {
                logError(new Error('Failed to connect to backend'), '[TFCBM Manager]');
                return false;
            }

            // Set up message handlers
            this._setupMessageHandlers();

            // Create panel
            this._panel = new GnomeSidePanel(this._alignment);

            // Set up panel callbacks
            this._panel.onItemClick(this._onItemClick.bind(this));

            // Fetch initial history
            await this._ipcClient.getHistory(20, 0);

            this._isInitialized = true;
            log('[TFCBM Manager] Initialized successfully');

            return true;

        } catch (e) {
            logError(e, '[TFCBM Manager] Initialization failed');
            this._cleanup();
            return false;
        }
    }

    /**
     * Set up IPC message handlers
     */
    _setupMessageHandlers() {
        // Handle history response
        this._ipcClient.on('history', (message) => {
            log(`[TFCBM Manager] Received history: ${message.items.length} items`);

            // Clear existing items
            this._panel.clearItems();

            // Add items to panel
            message.items.forEach(item => {
                this._panel.addItem(item);
            });
        });

        // Handle new item broadcast
        this._ipcClient.on('new_item', (message) => {
            log('[TFCBM Manager] Received new item');

            if (message.item) {
                this._panel.addItem(message.item);
            }
        });

        // Handle disconnect
        this._ipcClient.on('disconnect', () => {
            log('[TFCBM Manager] Backend disconnected');
            // Could show notification or auto-reconnect here
        });
    }

    /**
     * Handle item click - copy to clipboard and hide panel
     * @param {Object} item Clipboard item
     */
    _onItemClick(item) {
        log(`[TFCBM Manager] Item clicked: ${item.type}`);

        try {
            // Copy content to clipboard based on type
            if (item.type === 'text' || item.type === 'url') {
                this._clipboard.set_text(St.ClipboardType.CLIPBOARD, item.content);
                log('[TFCBM Manager] Copied text to clipboard');

            } else if (item.type === 'file') {
                // For files, copy the file name for now
                // TODO: Implement proper file content copying
                const fileName = item.content?.name || 'File';
                this._clipboard.set_text(St.ClipboardType.CLIPBOARD, fileName);
                log('[TFCBM Manager] Copied file name to clipboard');

            } else if (item.type.startsWith('image/')) {
                // For images, we'd need the full image data
                // For now, just log that we can't copy it directly
                log('[TFCBM Manager] Image copying not yet implemented');
                // TODO: Request full image from backend and copy to clipboard
            }

            // Hide panel after copying
            this._panel.hide();

        } catch (e) {
            logError(e, '[TFCBM Manager] Failed to copy to clipboard');
        }
    }

    /**
     * Toggle panel visibility
     */
    toggle() {
        if (!this._isInitialized || !this._panel) {
            log('[TFCBM Manager] Cannot toggle: not initialized');
            return;
        }

        this._panel.toggle();
    }

    /**
     * Show panel
     */
    show() {
        if (!this._isInitialized || !this._panel) {
            log('[TFCBM Manager] Cannot show: not initialized');
            return;
        }

        this._panel.show();
    }

    /**
     * Hide panel
     */
    hide() {
        if (!this._isInitialized || !this._panel) {
            return;
        }

        this._panel.hide();
    }

    /**
     * Check if panel is visible
     * @returns {boolean} Visibility status
     */
    isVisible() {
        return this._panel?.isVisible() || false;
    }

    /**
     * Update panel alignment
     * @param {string} alignment 'left' or 'right'
     */
    setAlignment(alignment) {
        this._alignment = alignment;

        if (this._panel) {
            this._panel.setAlignment(alignment);
        }
    }

    /**
     * Clean up resources
     */
    _cleanup() {
        if (this._ipcClient) {
            this._ipcClient.disconnect();
            this._ipcClient = null;
        }

        if (this._panel) {
            this._panel.destroy();
            this._panel = null;
        }

        this._isInitialized = false;
    }

    /**
     * Destroy manager and clean up
     */
    destroy() {
        log('[TFCBM Manager] Destroying');
        this._cleanup();
    }
}
