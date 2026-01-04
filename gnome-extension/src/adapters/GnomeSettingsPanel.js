/**
 * GNOME Settings Panel
 *
 * Displays application settings in the side panel
 * Syncs with backend via IPC
 */

import St from 'gi://St';
import Clutter from 'gi://Clutter';

export class GnomeSettingsPanel {
    constructor(ipcClient) {
        this._ipcClient = ipcClient;
        this._settings = null;
        this._panel = null;

        this._buildUI();
    }

    /**
     * Build the settings UI
     */
    _buildUI() {
        this._panel = new St.BoxLayout({
            style_class: 'tfcbm-settings-panel',
            vertical: true,
            style: 'padding: 16px; spacing: 12px;'
        });

        // Title
        const title = new St.Label({
            text: 'Settings',
            style: 'font-size: 18px; font-weight: bold; margin-bottom: 12px;'
        });
        this._panel.add_child(title);

        // Settings will be populated when loaded
        this._settingsContainer = new St.BoxLayout({
            vertical: true,
            style: 'spacing: 16px;'
        });
        this._panel.add_child(this._settingsContainer);
    }

    /**
     * Load settings from backend
     */
    async loadSettings() {
        await this._ipcClient.getSettings();
    }

    /**
     * Update settings display
     * @param {Object} settings Settings object from backend
     */
    updateSettings(settings) {
        this._settings = settings;
        this._settingsContainer.destroy_all_children();

        // Build settings UI
        this._buildDisplaySettings(settings.display);
        this._buildRetentionSettings(settings.retention);
        this._buildClipboardSettings(settings.clipboard);
        this._buildUISettings(settings.ui);
    }

    /**
     * Build display settings section
     */
    _buildDisplaySettings(display) {
        const group = this._createGroup('Display');

        // Max page length
        group.add_child(this._createNumberSetting(
            'Items per page',
            display.max_page_length,
            1,
            100,
            (value) => this._updateSetting({ display: { max_page_length: value } })
        ));

        this._settingsContainer.add_child(group);
    }

    /**
     * Build retention settings section
     */
    _buildRetentionSettings(retention) {
        const group = this._createGroup('Retention');

        // Enabled toggle
        group.add_child(this._createToggleSetting(
            'Auto cleanup',
            retention.enabled,
            (value) => this._updateSetting({ retention: { enabled: value } })
        ));

        // Max items
        group.add_child(this._createNumberSetting(
            'Maximum items',
            retention.max_items,
            10,
            10000,
            (value) => this._updateSetting({ retention: { max_items: value } })
        ));

        this._settingsContainer.add_child(group);
    }

    /**
     * Build clipboard settings section
     */
    _buildClipboardSettings(clipboard) {
        const group = this._createGroup('Clipboard');

        // Refocus on copy
        group.add_child(this._createToggleSetting(
            'Refocus on copy',
            clipboard.refocus_on_copy,
            (value) => this._updateSetting({ clipboard: { refocus_on_copy: value } })
        ));

        this._settingsContainer.add_child(group);
    }

    /**
     * Build UI settings section
     */
    _buildUISettings(ui) {
        const group = this._createGroup('UI Mode');

        // Mode selection
        const modeBox = new St.BoxLayout({
            vertical: false,
            style: 'spacing: 8px; margin-bottom: 8px;'
        });

        const modeLabel = new St.Label({
            text: 'Display mode:',
            style: 'min-width: 120px;'
        });
        modeBox.add_child(modeLabel);

        const modeValue = new St.Label({
            text: ui.mode === 'sidepanel' ? 'Side Panel' : 'Windowed',
            style: 'color: #999;'
        });
        modeBox.add_child(modeValue);

        group.add_child(modeBox);

        // Alignment (if sidepanel)
        if (ui.mode === 'sidepanel') {
            const alignBox = new St.BoxLayout({
                vertical: false,
                style: 'spacing: 8px;'
            });

            const alignLabel = new St.Label({
                text: 'Panel position:',
                style: 'min-width: 120px;'
            });
            alignBox.add_child(alignLabel);

            // Left/Right buttons
            const leftBtn = new St.Button({
                label: 'Left',
                style_class: ui.sidepanel_alignment === 'left' ? 'tfcbm-btn-active' : 'tfcbm-btn',
                style: 'padding: 6px 12px; margin-right: 4px;'
            });
            leftBtn.connect('clicked', () => {
                this._updateSetting({ ui: { sidepanel_alignment: 'left' } });
            });

            const rightBtn = new St.Button({
                label: 'Right',
                style_class: ui.sidepanel_alignment === 'right' ? 'tfcbm-btn-active' : 'tfcbm-btn',
                style: 'padding: 6px 12px;'
            });
            rightBtn.connect('clicked', () => {
                this._updateSetting({ ui: { sidepanel_alignment: 'right' } });
            });

            alignBox.add_child(leftBtn);
            alignBox.add_child(rightBtn);

            group.add_child(alignBox);
        }

        const note = new St.Label({
            text: 'Note: UI mode can be changed in the GTK app settings',
            style: 'font-size: 11px; color: #999; margin-top: 8px;'
        });
        group.add_child(note);

        this._settingsContainer.add_child(group);
    }

    /**
     * Create a settings group
     */
    _createGroup(title) {
        const group = new St.BoxLayout({
            vertical: true,
            style: 'padding: 12px; background-color: rgba(255,255,255,0.05); border-radius: 8px; spacing: 8px;'
        });

        const titleLabel = new St.Label({
            text: title,
            style: 'font-weight: bold; font-size: 14px; margin-bottom: 4px;'
        });
        group.add_child(titleLabel);

        return group;
    }

    /**
     * Create a toggle setting row
     */
    _createToggleSetting(label, value, onChange) {
        const row = new St.BoxLayout({
            vertical: false,
            style: 'spacing: 8px;'
        });

        const labelWidget = new St.Label({
            text: label,
            style: 'min-width: 120px;'
        });
        row.add_child(labelWidget);

        const toggle = new St.Button({
            label: value ? 'ON' : 'OFF',
            style_class: value ? 'tfcbm-toggle-on' : 'tfcbm-toggle-off',
            style: 'padding: 6px 16px; min-width: 60px;'
        });

        toggle.connect('clicked', () => {
            const newValue = !value;
            toggle.set_label(newValue ? 'ON' : 'OFF');
            toggle.style_class = newValue ? 'tfcbm-toggle-on' : 'tfcbm-toggle-off';
            onChange(newValue);
        });

        row.add_child(toggle);

        return row;
    }

    /**
     * Create a number setting row
     */
    _createNumberSetting(label, value, min, max, onChange) {
        const row = new St.BoxLayout({
            vertical: false,
            style: 'spacing: 8px;'
        });

        const labelWidget = new St.Label({
            text: label,
            style: 'min-width: 120px;'
        });
        row.add_child(labelWidget);

        const valueBox = new St.BoxLayout({
            vertical: false,
            style: 'spacing: 4px;'
        });

        const decreaseBtn = new St.Button({
            label: '−',
            style: 'padding: 6px 12px; min-width: 40px;'
        });

        const valueLabel = new St.Label({
            text: value.toString(),
            style: 'padding: 6px 12px; min-width: 60px; text-align: center;'
        });

        const increaseBtn = new St.Button({
            label: '+',
            style: 'padding: 6px 12px; min-width: 40px;'
        });

        let currentValue = value;

        decreaseBtn.connect('clicked', () => {
            if (currentValue > min) {
                currentValue--;
                valueLabel.set_text(currentValue.toString());
                onChange(currentValue);
            }
        });

        increaseBtn.connect('clicked', () => {
            if (currentValue < max) {
                currentValue++;
                valueLabel.set_text(currentValue.toString());
                onChange(currentValue);
            }
        });

        valueBox.add_child(decreaseBtn);
        valueBox.add_child(valueLabel);
        valueBox.add_child(increaseBtn);

        row.add_child(valueBox);

        return row;
    }

    /**
     * Update a setting on the backend
     */
    async _updateSetting(settingUpdate) {
        log(`[TFCBM Settings] Updating: ${JSON.stringify(settingUpdate)}`);
        await this._ipcClient.updateSettings(settingUpdate);
    }

    /**
     * Get the panel actor
     */
    getActor() {
        return this._panel;
    }

    /**
     * Destroy the panel
     */
    destroy() {
        if (this._panel) {
            this._panel.destroy();
            this._panel = null;
        }
    }
}
