/**
 * GNOME Side Panel Widget
 *
 * Renders clipboard items in a side panel that slides in from screen edge
 * Uses GNOME Shell's St (Shell Toolkit) and Clutter for UI and animations
 *
 * Architecture: Adapter pattern - implements UI using GNOME Shell APIs
 */

import St from 'gi://St';
import Clutter from 'gi://Clutter';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import { GnomeSettingsPanel } from './GnomeSettingsPanel.js';

export class GnomeSidePanel {
    constructor(alignment = 'right', ipcClient) {
        this._alignment = alignment; // 'left' or 'right'
        this._isVisible = false;
        this._panel = null;
        this._itemsContainer = null;
        this._contentContainer = null;
        this._items = [];
        this._onItemClickCallback = null;
        this._ipcClient = ipcClient;
        this._currentTab = 'history'; // 'history' or 'settings'
        this._settingsPanel = null;

        this._buildUI();
    }

    /**
     * Build the panel UI
     */
    _buildUI() {
        // Main panel container
        this._panel = new St.BoxLayout({
            style_class: 'tfcbm-side-panel',
            vertical: true,
            reactive: true,
            can_focus: true,
            track_hover: true,
        });

        // Set panel styling
        this._panel.set_style(`
            background-color: rgba(0, 0, 0, 0.85);
            border-radius: ${this._alignment === 'left' ? '0 16px 16px 0' : '16px 0 0 16px'};
            padding: 16px;
            min-width: 400px;
            max-width: 400px;
        `);

        // Header with tabs
        const header = new St.BoxLayout({
            style_class: 'tfcbm-panel-header',
            vertical: true,
            style: 'margin-bottom: 16px;',
        });

        // Tab bar
        const tabBar = new St.BoxLayout({
            vertical: false,
            style: 'spacing: 8px; margin-bottom: 12px;',
        });

        this._historyTab = new St.Button({
            label: 'Clipboard',
            style_class: 'tfcbm-tab-active',
            style: 'padding: 8px 16px; border-radius: 6px;',
        });
        this._historyTab.connect('clicked', () => this._switchTab('history'));

        this._settingsTab = new St.Button({
            label: 'Settings',
            style_class: 'tfcbm-tab',
            style: 'padding: 8px 16px; border-radius: 6px;',
        });
        this._settingsTab.connect('clicked', () => this._switchTab('settings'));

        tabBar.add_child(this._historyTab);
        tabBar.add_child(this._settingsTab);

        header.add_child(tabBar);
        this._panel.add_child(header);

        // Content container (switches between history and settings)
        this._contentContainer = new St.Bin({
            style: 'min-height: 0;',
        });
        this._panel.add_child(this._contentContainer);

        // Build history view
        const scrollView = new St.ScrollView({
            style_class: 'tfcbm-scroll-view',
            hscrollbar_policy: St.PolicyType.NEVER,
            vscrollbar_policy: St.PolicyType.AUTOMATIC,
        });

        this._itemsContainer = new St.BoxLayout({
            style_class: 'tfcbm-items-container',
            vertical: true,
            style: 'spacing: 8px;',
        });

        scrollView.add_child(this._itemsContainer);

        // Set history as default view
        this._historyView = scrollView;
        this._contentContainer.set_child(this._historyView);

        // Position panel off-screen initially
        this._panel.translation_x = this._alignment === 'right'
            ? 400  // Off-screen to the right
            : -400; // Off-screen to the left

        // Set panel position on screen (below top bar to avoid covering tray)
        const monitor = Main.layoutManager.primaryMonitor;
        const panelBox = Main.layoutManager.panelBox;
        const topBarHeight = panelBox.height;

        this._panel.set_position(
            this._alignment === 'right'
                ? monitor.x + monitor.width - 400
                : monitor.x,
            monitor.y + topBarHeight  // Start below the top bar
        );

        // Set height to fill screen minus top bar
        this._panel.set_height(monitor.height - topBarHeight);

        // Add to UI group (top-level container)
        Main.uiGroup.add_child(this._panel);

        // Handle key press for navigation
        this._panel.connect('key-press-event', this._onKeyPress.bind(this));
    }

    /**
     * Handle key press events
     * @param {Clutter.Actor} actor The panel actor
     * @param {Clutter.Event} event Key event
     * @returns {boolean} True if handled
     */
    _onKeyPress(actor, event) {
        const symbol = event.get_key_symbol();

        switch (symbol) {
            case Clutter.KEY_Escape:
                // Hide panel on Escape
                this.hide();
                return Clutter.EVENT_STOP;

            case Clutter.KEY_Down:
            case Clutter.KEY_Up:
                // TODO: Implement arrow key navigation
                return Clutter.EVENT_STOP;

            case Clutter.KEY_Return:
            case Clutter.KEY_KP_Enter:
                // TODO: Activate selected item
                return Clutter.EVENT_STOP;

            default:
                return Clutter.EVENT_PROPAGATE;
        }
    }

    /**
     * Show panel with smooth slide-in animation
     */
    show() {
        if (this._isVisible) return;

        this._isVisible = true;
        this._panel.show();
        this._panel.grab_key_focus();

        // Slide in animation
        this._panel.ease({
            translation_x: 0,
            duration: 250,
            mode: Clutter.AnimationMode.EASE_OUT_QUAD,
            onComplete: () => {
                log('[TFCBM Panel] Shown');
            }
        });
    }

    /**
     * Hide panel with smooth slide-out animation
     */
    hide() {
        if (!this._isVisible) return;

        this._isVisible = false;

        // Slide out animation
        this._panel.ease({
            translation_x: this._alignment === 'right' ? 400 : -400,
            duration: 250,
            mode: Clutter.AnimationMode.EASE_OUT_QUAD,
            onComplete: () => {
                this._panel.hide();
                log('[TFCBM Panel] Hidden');
            }
        });
    }

    /**
     * Toggle panel visibility
     */
    toggle() {
        if (this._isVisible) {
            this.hide();
        } else {
            this.show();
        }
    }

    /**
     * Check if panel is visible
     * @returns {boolean} Visibility status
     */
    isVisible() {
        return this._isVisible;
    }

    /**
     * Add clipboard item to panel
     * @param {Object} item Clipboard item from backend
     */
    addItem(item) {
        // Create item button
        const itemButton = new St.Button({
            style_class: 'tfcbm-item-button',
            reactive: true,
            can_focus: true,
            track_hover: true,
        });

        itemButton.set_style(`
            background-color: rgba(255, 255, 255, 0.1);
            border-radius: 8px;
            padding: 12px;
            margin-bottom: 4px;
            min-height: 60px;
        `);

        // Create item layout
        const itemLayout = new St.BoxLayout({
            vertical: true,
            style: 'spacing: 4px;',
        });

        // Item type icon and preview
        const headerBox = new St.BoxLayout({
            vertical: false,
            style: 'spacing: 8px;',
        });

        // Icon based on type
        const icon = new St.Icon({
            icon_name: this._getIconForType(item.type),
            icon_size: 24,
            style: 'margin-right: 8px;',
        });
        headerBox.add_child(icon);

        // Content preview (truncated)
        const preview = new St.Label({
            text: this._getPreviewText(item),
            style: 'font-size: 14px; color: #ffffff;',
        });
        preview.clutter_text.set_line_wrap(true);
        preview.clutter_text.set_line_wrap_mode(2); // PANGO_WRAP_WORD
        preview.clutter_text.set_ellipsize(3); // PANGO_ELLIPSIZE_END
        preview.clutter_text.set_max_length(100);

        headerBox.add_child(preview);
        itemLayout.add_child(headerBox);

        // Timestamp
        const timestamp = new St.Label({
            text: this._formatTimestamp(item.timestamp),
            style: 'font-size: 11px; color: rgba(255, 255, 255, 0.6);',
        });
        itemLayout.add_child(timestamp);

        itemButton.set_child(itemLayout);

        // Handle click
        itemButton.connect('clicked', () => {
            if (this._onItemClickCallback) {
                this._onItemClickCallback(item);
            }
        });

        // Add to container (prepend - newest first)
        this._itemsContainer.insert_child_at_index(itemButton, 0);
        this._items.unshift({ item, button: itemButton });

        // Limit to 20 items
        if (this._items.length > 20) {
            const removed = this._items.pop();
            this._itemsContainer.remove_child(removed.button);
            removed.button.destroy();
        }
    }

    /**
     * Clear all items from panel
     */
    clearItems() {
        this._items.forEach(({ button }) => {
            this._itemsContainer.remove_child(button);
            button.destroy();
        });
        this._items = [];
    }

    /**
     * Set callback for item click
     * @param {Function} callback Called when item is clicked
     */
    onItemClick(callback) {
        this._onItemClickCallback = callback;
    }

    /**
     * Get icon name for item type
     * @param {string} type Item type
     * @returns {string} Icon name
     */
    _getIconForType(type) {
        switch (type) {
            case 'text':
                return 'text-x-generic-symbolic';
            case 'url':
                return 'web-browser-symbolic';
            case 'file':
                return 'document-open-symbolic';
            case 'image/png':
            case 'image/jpeg':
            case 'screenshot':
                return 'image-x-generic-symbolic';
            default:
                return 'edit-paste-symbolic';
        }
    }

    /**
     * Get preview text for item
     * @param {Object} item Clipboard item
     * @returns {string} Preview text
     */
    _getPreviewText(item) {
        if (item.type === 'text' || item.type === 'url') {
            return item.content || '(empty)';
        } else if (item.type === 'file') {
            return item.content?.name || 'File';
        } else {
            return `[${item.type}]`;
        }
    }

    /**
     * Format timestamp as relative time
     * @param {string} timestamp ISO timestamp
     * @returns {string} Formatted timestamp
     */
    _formatTimestamp(timestamp) {
        try {
            const date = new Date(timestamp);
            const now = new Date();
            const diffMs = now - date;
            const diffMins = Math.floor(diffMs / 60000);

            if (diffMins < 1) return 'Just now';
            if (diffMins < 60) return `${diffMins}m ago`;
            if (diffMins < 1440) return `${Math.floor(diffMins / 60)}h ago`;
            return `${Math.floor(diffMins / 1440)}d ago`;
        } catch (e) {
            return timestamp;
        }
    }

    /**
     * Update panel alignment (left/right)
     * @param {string} alignment 'left' or 'right'
     */
    setAlignment(alignment) {
        if (this._alignment === alignment) return;

        this._alignment = alignment;

        // Update border radius
        this._panel.set_style(`
            background-color: rgba(0, 0, 0, 0.85);
            border-radius: ${alignment === 'left' ? '0 16px 16px 0' : '16px 0 0 16px'};
            padding: 16px;
            min-width: 400px;
            max-width: 400px;
        `);

        // Update position
        const monitor = Main.layoutManager.primaryMonitor;
        this._panel.set_position(
            alignment === 'right'
                ? monitor.x + monitor.width - 400
                : monitor.x,
            monitor.y
        );

        // Update off-screen position for animations
        if (!this._isVisible) {
            this._panel.translation_x = alignment === 'right' ? 400 : -400;
        }
    }

    /**
     * Switch between pages (clipboard history or settings)
     * @param {string} pageName 'history' or 'settings'
     */
    _switchTab(pageName) {
        if (this._currentTab === pageName) return;

        log(`[TFCBM Panel] Switching to ${pageName} page`);
        this._currentTab = pageName;

        // Update button styles
        if (pageName === 'history') {
            this._historyTab.style_class = 'tfcbm-tab-active';
            this._settingsTab.style_class = 'tfcbm-tab';

            // Show history view
            this._contentContainer.set_child(this._historyView);
        } else if (pageName === 'settings') {
            this._historyTab.style_class = 'tfcbm-tab';
            this._settingsTab.style_class = 'tfcbm-tab-active';

            // Create settings panel if needed
            if (!this._settingsPanel) {
                this._settingsPanel = new GnomeSettingsPanel(this._ipcClient);

                // Register handler for settings response
                this._ipcClient.on('settings', (settings) => {
                    log(`[TFCBM Panel] Received settings`);
                    this._settingsPanel.updateSettings(settings);
                });

                // Register handler for settings updated
                this._ipcClient.on('settings_updated', (data) => {
                    log(`[TFCBM Panel] Settings updated: ${data.success}`);
                    if (data.success && data.settings) {
                        this._settingsPanel.updateSettings(data.settings);
                    }
                });

                // Load settings from backend
                this._settingsPanel.loadSettings();
            }

            // Show settings page
            this._contentContainer.set_child(this._settingsPanel.getActor());
        }
    }

    /**
     * Destroy panel and clean up
     */
    destroy() {
        if (this._settingsPanel) {
            this._settingsPanel.destroy();
            this._settingsPanel = null;
        }

        if (this._panel) {
            Main.uiGroup.remove_child(this._panel);
            this._panel.destroy();
            this._panel = null;
        }

        this._itemsContainer = null;
        this._items = [];
        this._onItemClickCallback = null;
    }
}
