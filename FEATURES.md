# TFCBM New Features

## Overview

TFCBM now includes dynamic keyboard shortcut recording and a system tray integration!

## Features Implemented

### 1. Dynamic Keyboard Shortcut Recording

The settings screen now has a **Keyboard Shortcut** section (first setting) where you can:

- **View current shortcut**: See the currently configured global shortcut
- **Record new shortcut**: Click "Record" button and press any key combination
- **Instant application**: Changes are immediately applied to the GNOME extension

**Location**: Settings → Keyboard Shortcut (at the top)

**Architecture**:
- `ui/domain/keyboard.py` - Domain models for keyboard shortcuts
- `ui/interfaces/keyboard_input.py` - Keyboard event interface
- `ui/interfaces/settings.py` - Settings storage interface
- `ui/infrastructure/gtk_keyboard_parser.py` - GTK keyboard event parser
- `ui/infrastructure/gsettings_store.py` - GSettings storage implementation
- `ui/services/shortcut_service.py` - Shortcut recording service
- `ui/pages/settings_page.py` - Settings UI with recorder widget

### 2. System Tray Icon

The GNOME extension now displays a tray icon in the system panel with:

**Left-click**: Toggle TFCBM window (show/hide/focus)

**Right-click menu**:
- **Settings**: Opens TFCBM settings page
- **About**: Opens the about dialog

**Icon**: Uses `resouces/tfcbm.svg` (falls back to clipboard icon if not found)

**Location**: Top panel system tray area

### 3. Unified Setup Script

New `run.sh` script that handles everything:

```bash
./run.sh
```

**What it does**:
- ✓ Checks for GNOME desktop environment
- ✓ Installs system dependencies (with prompt)
- ✓ Creates Python virtual environment
- ✓ Installs Python dependencies
- ✓ Compiles GSettings schemas
- ✓ Installs GNOME extension
- ✓ Enables extension (prompts for logout if needed)
- ✓ Starts backend server
- ✓ Launches UI

**First-time setup**: Just run `./run.sh` and follow the prompts!

## Usage

### Setting Up TFCBM

```bash
cd /path/to/TFCBM
./run.sh
```

The script will guide you through any required setup steps.

### Changing the Keyboard Shortcut

1. Launch TFCBM (use current shortcut or tray icon)
2. Go to Settings tab
3. Click "Record" in the Keyboard Shortcut section
4. Press your desired key combination
5. The new shortcut is applied immediately!

### Using the Tray Icon

- **Left-click**: Toggle TFCBM window
- **Right-click**: Access Settings and About

## Technical Details

### Keyboard Shortcut System

The keyboard shortcut system follows a clean architecture pattern inspired by the test_app:

**Domain Layer**: Pure domain models with no dependencies
- `KeyboardShortcut` value object with GTK/GSettings conversions

**Interface Layer**: Abstract protocols for dependency inversion
- `IKeyboardEventParser` - Parse keyboard events
- `ISettingsStore` - Store/retrieve shortcuts

**Infrastructure Layer**: Concrete implementations
- `GtkKeyboardParser` - GTK4 event parsing
- `GSettingsStore` - GSettings backend storage

**Application Layer**: Business logic
- `ShortcutService` - Recording and applying shortcuts with observer pattern

### Extension Integration

The GNOME extension dynamically reads shortcuts from GSettings:

```javascript
Main.wm.addKeybinding(
    'toggle-tfcbm-ui',
    this._settings,  // Automatically syncs with GSettings
    0,
    1,
    () => this._toggleUI()
);
```

When you change the shortcut in settings, the extension picks it up automatically!

### System Tray Implementation

Uses GNOME Shell's PanelMenu API:

```javascript
this._indicator = new PanelMenu.Button(0.0, 'TFCBM', false);
// Left-click handler
this._indicator.connect('button-press-event', (actor, event) => {
    if (event.get_button() === 1) {
        this._toggleUI();
    }
});
// Right-click menu
this._indicator.menu.addMenuItem(settingsItem);
this._indicator.menu.addMenuItem(aboutItem);
```

## Testing

Run integration tests:

```bash
./test_integration.sh
```

This verifies:
- Python keyboard shortcut infrastructure
- Extension syntax
- Schema compilation
- Resources availability

## Files Changed/Added

### New Files
- `ui/domain/keyboard.py` - Keyboard shortcut domain models
- `ui/domain/__init__.py`
- `ui/interfaces/keyboard_input.py` - Keyboard input interfaces
- `ui/interfaces/settings.py` - Settings storage interface
- `ui/interfaces/__init__.py`
- `ui/infrastructure/gtk_keyboard_parser.py` - GTK parser implementation
- `ui/infrastructure/gsettings_store.py` - GSettings storage
- `ui/infrastructure/__init__.py`
- `ui/services/shortcut_service.py` - Shortcut service
- `run.sh` - Unified setup and launch script
- `test_integration.sh` - Integration test script

### Modified Files
- `ui/pages/settings_page.py` - Added shortcut recorder UI
- `gnome-extension/extension.js` - Added tray icon and menu
- `gnome-extension/schemas/org.gnome.shell.extensions.simple-clipboard.gschema.xml` - Schema for shortcuts

## Next Steps

You can now:

1. Run `./run.sh` to start everything
2. Try changing the keyboard shortcut in Settings
3. Use the tray icon to quickly toggle TFCBM
4. Enjoy the improved workflow!
