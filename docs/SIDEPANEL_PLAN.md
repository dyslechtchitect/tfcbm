# GNOME Extension Side Panel UI - Implementation Plan

## Overview
Add a GNOME Shell side panel UI mode as an alternative to the GTK windowed UI, backed by contract tests to ensure backend compatibility.

**Requirements:**
- ✅ Wayland-native (no X11 dependencies)
- ✅ GNOME HIG compliant (Human Interface Guidelines)
- ✅ Flatpak sandboxed (portal-based communication)
- ✅ Overlay side panel (doesn't resize windows, floats above)
- ✅ Extension Shell 45+ compatible

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Python Backend (main.py)                  │
│  ┌────────────────┬──────────────┬─────────────────────┐    │
│  │ IPC Service    │ DB Service   │ Clipboard Service   │    │
│  │ (UNIX socket)  │ (SQLite)     │ (Business Logic)    │    │
│  └────────────────┴──────────────┴─────────────────────┘    │
│           ▲                           ▲                      │
│           │ UNIX socket IPC           │ DBus                 │
│           │                           │                      │
└───────────┼───────────────────────────┼──────────────────────┘
            │                           │
    ┌───────┴────────┐         ┌────────┴──────────┐
    │   GTK UI       │         │ GNOME Extension   │
    │  (windowed)    │         │   (sidepanel)     │
    └────────────────┘         └───────────────────┘
```

## Phase 1: Contract Definition & Testing Infrastructure

### 1.1 Define DBus Contract (Week 1)

**File:** `server/src/dbus_contract.xml`
```xml
<!-- Introspection format for contract definition -->
<node>
  <interface name="org.tfcbm.ClipboardService">
    <!-- State queries -->
    <method name="GetHistory">
      <arg name="offset" type="i" direction="in"/>
      <arg name="limit" type="i" direction="in"/>
      <arg name="filters" type="as" direction="in"/>
      <arg name="items" type="aa{sv}" direction="out"/>
      <arg name="total_count" type="i" direction="out"/>
    </method>

    <method name="GetUIMode">
      <arg name="mode" type="s" direction="out"/>
      <arg name="alignment" type="s" direction="out"/>
    </method>

    <method name="SetUIMode">
      <arg name="mode" type="s" direction="in"/>
      <arg name="alignment" type="s" direction="in"/>
      <arg name="success" type="b" direction="out"/>
    </method>

    <!-- Signals -->
    <signal name="ClipboardChanged">
      <arg name="item" type="a{sv}"/>
    </signal>

    <signal name="UIModeChanged">
      <arg name="mode" type="s"/>
      <arg name="alignment" type="s"/>
    </signal>
  </interface>
</node>
```

**Alternative: JSON Schema for IPC contract**
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "TFCBM IPC Contract v1",
  "definitions": {
    "ClipboardItem": {
      "type": "object",
      "required": ["id", "type", "timestamp"],
      "properties": {
        "id": {"type": "integer"},
        "type": {"enum": ["text", "url", "image/png", "file"]},
        "content": {"type": ["string", "null"]},
        "timestamp": {"type": "string", "format": "date-time"}
      }
    },
    "UIMode": {
      "type": "object",
      "properties": {
        "mode": {"enum": ["windowed", "sidepanel"]},
        "alignment": {"enum": ["left", "right", "none"]}
      }
    }
  },
  "messages": {
    "get_history": {
      "request": {
        "action": {"const": "get_history"},
        "offset": {"type": "integer", "minimum": 0},
        "limit": {"type": "integer", "minimum": 1, "maximum": 100}
      },
      "response": {
        "type": "history",
        "items": {"type": "array", "items": {"$ref": "#/definitions/ClipboardItem"}},
        "total_count": {"type": "integer"}
      }
    }
  }
}
```

**Decision:** Use JSON Schema for IPC contract, DBus XML for extension↔backend.
- IPC is already JSON-based (UNIX socket)
- DBus is only for extension→backend signals
- Easier to validate in Python (jsonschema library)

### 1.2 Backend Contract Tests (Week 1)

**File:** `server/test/contract/test_ipc_contract.py`
```python
import pytest
import json
from jsonschema import validate, ValidationError
from server.src.services.ipc_service import IPCService

class TestIPCContract:
    @pytest.fixture
    def contract_schema(self):
        with open('server/src/ipc_contract.json') as f:
            return json.load(f)

    def test_get_history_request_shape(self, contract_schema):
        """Validate get_history request conforms to contract"""
        request = {
            "action": "get_history",
            "offset": 0,
            "limit": 20
        }
        # Should not raise ValidationError
        validate(request, contract_schema['messages']['get_history']['request'])

    def test_get_history_response_shape(self, ipc_service, contract_schema):
        """Validate get_history response conforms to contract"""
        # Call real backend
        response = ipc_service.get_history(offset=0, limit=5)

        # Validate against schema
        validate(response, contract_schema['messages']['get_history']['response'])

    def test_new_item_signal_shape(self, contract_schema):
        """Validate new_item broadcast conforms to contract"""
        signal = {
            "type": "new_item",
            "item": {
                "id": 1,
                "type": "text",
                "content": "test",
                "timestamp": "2024-01-01T00:00:00"
            }
        }
        validate(signal, contract_schema['messages']['new_item']['signal'])

    def test_backwards_compatibility(self):
        """Ensure old clients can still connect"""
        # Old client sends request without new fields
        old_request = {"action": "get_history"}
        # Should still work with defaults
        response = ipc_service.handle_get_history(old_request)
        assert response['type'] == 'history'
```

### 1.3 Extension Contract Tests (Week 1-2)

**File:** `gnome-extension/test/contractTest.js`
```javascript
// GJS testing with jasmine-gjs or custom test runner
const { GLib } = imports.gi;

// Mock DBus proxy
class MockDBusProxy {
    constructor() {
        this.responses = new Map();
    }

    setResponse(method, response) {
        this.responses.set(method, response);
    }

    callSync(method, params) {
        return this.responses.get(method) || null;
    }
}

describe('DBus Contract', () => {
    let proxy;

    beforeEach(() => {
        proxy = new MockDBusProxy();
    });

    it('should handle GetHistory response shape', () => {
        const mockResponse = {
            items: [
                { id: 1, type: 'text', content: 'test', timestamp: '2024-01-01T00:00:00' }
            ],
            total_count: 1
        };
        proxy.setResponse('GetHistory', mockResponse);

        const result = proxy.callSync('GetHistory', [0, 20]);

        expect(result.items).toBeDefined();
        expect(result.total_count).toBeGreaterThanOrEqual(0);
        expect(result.items[0].id).toBeDefined();
    });

    it('should validate UI mode values', () => {
        const validModes = ['windowed', 'sidepanel'];
        const validAlignments = ['left', 'right', 'none'];

        validModes.forEach(mode => {
            expect(() => validateUIMode(mode, 'left')).not.toThrow();
        });
    });
});
```

## Phase 2: Settings UI (Week 2)

### 2.1 Add UI Mode Settings to Backend

**File:** `server/src/services/settings_service.py`
```python
class SettingsService:
    def __init__(self):
        self.defaults = {
            # ... existing settings ...
            "ui.mode": "windowed",  # or "sidepanel"
            "ui.sidepanel_alignment": "right",  # or "left"
        }
```

### 2.2 GTK Settings Page

**File:** `ui/pages/settings_page.py`
```python
def _build_ui_mode_group(self) -> Adw.PreferencesGroup:
    """Build UI mode settings section."""
    group = Adw.PreferencesGroup()
    group.set_title("UI Mode")

    # Mode selector
    mode_row = Adw.ComboRow()
    mode_row.set_title("Display Mode")
    mode_row.set_subtitle("How TFCBM appears on your desktop")

    model = Gtk.StringList()
    model.append("Windowed (Separate Window)")
    model.append("Side Panel (GNOME Extension)")
    mode_row.set_model(model)

    # Alignment (only visible when sidepanel selected)
    alignment_row = Adw.ActionRow()
    alignment_row.set_title("Panel Alignment")

    left_btn = Gtk.ToggleButton()
    left_btn.set_icon_name("go-first-symbolic")
    right_btn = Gtk.ToggleButton()
    right_btn.set_icon_name("go-last-symbolic")

    # ... connect signals ...

    return group
```

## Phase 3: Extension Side Panel (Week 3-4)

### 3.1 Extension Architecture

```
gnome-extension/
├── extension.js          # Entry point, manages lifecycle
├── sidePanel.js          # Main panel container
├── clipboardList.js      # List view component
├── clipboardItem.js      # Individual item widget
├── dbusClient.js         # DBus/IPC communication
├── stateManager.js       # Local state cache
└── test/
    ├── contractTest.js
    └── integrationTest.js
```

### 3.2 Side Panel Widget

**File:** `gnome-extension/sidePanel.js`
```javascript
const { St, Clutter } = imports.gi;
const Main = imports.ui.main;

class ClipboardSidePanel {
    constructor(alignment = 'right') {
        this.alignment = alignment;
        this._buildUI();
        this._connectSignals();
    }

    _buildUI() {
        // Create panel container (overlay, doesn't affect window layout)
        this.actor = new St.BoxLayout({
            style_class: 'tfcbm-sidepanel',
            vertical: true,
            width: 380,  // ~400dp in GNOME HIG terms
            reactive: true,
            can_focus: true
        });

        // Position based on alignment
        const monitor = Main.layoutManager.primaryMonitor;
        this.actor.set_height(monitor.height);

        if (this.alignment === 'right') {
            this.actor.x = monitor.x + monitor.width - 380;
        } else {
            this.actor.x = monitor.x;
        }
        this.actor.y = monitor.y;

        // Add to overlay layer (NOT affectsStruts - true overlay behavior)
        Main.layoutManager.addChrome(this.actor, {
            affectsStruts: false,     // Overlay: floats above windows
            affectsInputRegion: true, // Captures mouse/touch events
            trackFullscreen: true     // Auto-hide in fullscreen
        });

        // Add shadow for depth (GNOME HIG: elevated surfaces)
        this.actor.add_style_class_name('background');
        this.actor.add_style_class_name('popup-menu');  // Reuse shell theme

        // Header bar
        this._buildHeader();

        // Scrollable content area
        this.scrollView = new St.ScrollView({
            style_class: 'tfcbm-scroll-view',
            hscrollbarPolicy: St.PolicyType.NEVER,
            vscrollbarPolicy: St.PolicyType.AUTOMATIC,
            overlay_scrollbars: true  // GNOME HIG: overlay scrollbars
        });

        this.list = new St.BoxLayout({
            vertical: true,
            style_class: 'tfcbm-list'
        });
        this.scrollView.add_actor(this.list);
        this.actor.add_child(this.scrollView);

        // Initially hidden
        this.actor.opacity = 0;
        this.actor.hide();
    }

    _buildHeader() {
        const header = new St.BoxLayout({
            style_class: 'tfcbm-header',
            vertical: false,
            x_expand: true
        });

        // Title
        const title = new St.Label({
            text: 'Clipboard History',
            style_class: 'tfcbm-title',
            y_align: Clutter.ActorAlign.CENTER
        });
        header.add_child(title);

        // Spacer
        header.add_child(new St.Widget({ x_expand: true }));

        // Close button (GNOME HIG: circular close button)
        const closeBtn = new St.Button({
            style_class: 'button',
            child: new St.Icon({
                icon_name: 'window-close-symbolic',
                icon_size: 16
            })
        });
        closeBtn.connect('clicked', () => this.hide());
        header.add_child(closeBtn);

        this.actor.add_child(header);
    }

    show() {
        this.actor.show();
        this.actor.ease({
            opacity: 255,
            duration: 200,
            mode: Clutter.AnimationMode.EASE_OUT_QUAD
        });
    }

    hide() {
        this.actor.ease({
            opacity: 0,
            duration: 200,
            mode: Clutter.AnimationMode.EASE_OUT_QUAD,
            onComplete: () => this.actor.hide()
        });
    }

    destroy() {
        Main.layoutManager.removeChrome(this.actor);
        this.actor.destroy();
    }
}
```

### 3.3 Mode-Aware Activation

**Important:** Tray icon and keyboard shortcut behavior depends on UI mode setting.

**File:** `gnome-extension/extension.js`
```javascript
class TFCBMExtension {
    constructor() {
        this.dbusClient = new DBusClient();
        this.sidePanel = null;
        this.currentMode = 'windowed';  // Default
    }

    enable() {
        // Load UI mode from backend
        this._loadUIMode();

        // Tray icon click handler
        this.trayIcon.connect('button-press-event', () => {
            this._handleActivation();
        });

        // Keyboard shortcut handler
        Main.wm.addKeybinding(
            'toggle-tfcbm-ui',
            this._settings,
            Meta.KeyBindingFlags.NONE,
            Shell.ActionMode.NORMAL,
            () => this._handleActivation()
        );
    }

    async _loadUIMode() {
        const mode = await this.dbusClient.getUIMode();
        this.currentMode = mode.mode;
        this.currentAlignment = mode.alignment;

        if (mode.mode === 'sidepanel' && !this.sidePanel) {
            this.sidePanel = new ClipboardSidePanel(mode.alignment);
        }
    }

    _handleActivation() {
        if (this.currentMode === 'windowed') {
            // Activate GTK window via DBus
            this.dbusClient.activateWindow();
        } else {
            // Toggle side panel
            if (this.sidePanel.actor.visible) {
                this.sidePanel.hide();
            } else {
                this.sidePanel.show();
            }
        }
    }

    // Listen for mode changes from backend
    _onUIModeChanged(mode, alignment) {
        this.currentMode = mode;
        this.currentAlignment = alignment;

        if (mode === 'sidepanel') {
            if (!this.sidePanel) {
                this.sidePanel = new ClipboardSidePanel(alignment);
            }
            // Hide GTK window if visible
            this.dbusClient.hideWindow();
        } else {
            // Destroy side panel, prepare for windowed mode
            if (this.sidePanel) {
                this.sidePanel.destroy();
                this.sidePanel = null;
            }
        }
    }
}
```

### 3.4 DBus Client for Extension

**File:** `gnome-extension/dbusClient.js`
```javascript
const { Gio } = imports.gi;

const DBusInterface = `
<node>
  <interface name="org.tfcbm.ClipboardService">
    <method name="GetHistory">
      <arg type="i" direction="in" name="offset"/>
      <arg type="i" direction="in" name="limit"/>
      <arg type="aa{sv}" direction="out" name="items"/>
    </method>
    <signal name="ClipboardChanged">
      <arg type="a{sv}" name="item"/>
    </signal>
  </interface>
</node>
`;

class DBusClient {
    constructor() {
        this.proxy = null;
        this._connect();
    }

    _connect() {
        const DBusProxy = Gio.DBusProxy.makeProxyWrapper(DBusInterface);
        this.proxy = new DBusProxy(
            Gio.DBus.session,
            'org.tfcbm.ClipboardService',
            '/org/tfcbm/ClipboardService'
        );

        // Connect to signals
        this.proxy.connectSignal('ClipboardChanged', (proxy, sender, [item]) => {
            this._onClipboardChanged(item);
        });
    }

    async getHistory(offset = 0, limit = 20) {
        try {
            const [items] = await this.proxy.GetHistoryAsync(offset, limit);
            return items;
        } catch (e) {
            logError(e, 'Failed to get clipboard history');
            return [];
        }
    }
}
```

## Phase 4: Integration & Contract Validation (Week 4)

### 4.1 End-to-End Contract Test

**File:** `server/test/integration/test_contract_e2e.py`
```python
def test_gtk_and_extension_receive_same_data(backend, gtk_client, extension_mock):
    """Ensure both UIs get identical data from backend"""
    # Backend broadcasts new item
    item = backend.add_clipboard_item("test", "text")

    # Both clients should receive identical payload
    gtk_received = gtk_client.get_last_broadcast()
    ext_received = extension_mock.get_last_dbus_signal()

    assert gtk_received['item']['id'] == ext_received['item']['id']
    assert gtk_received['item']['type'] == ext_received['item']['type']
```

## Versioning & Evolution

### Contract Version Header
```json
{
  "contract_version": "1.0.0",
  "compatible_with": ["1.0.x"]
}
```

### Evolution Rules
1. **Adding fields**: Always optional, include defaults
2. **Removing fields**: Deprecate for 2 versions minimum
3. **Changing types**: Introduce new field, deprecate old
4. **Breaking changes**: Bump major version, maintain backward compat layer

Example:
```python
# v1.0: type is string
{"type": "text"}

# v1.1: add enum validation but accept old format
{"type": "text", "item_type": "TEXT"}  # both accepted

# v2.0: remove old field
{"item_type": "TEXT"}  # only this accepted
```

## Testing Strategy Summary

| Layer | Tool | Focus |
|-------|------|-------|
| Contract Schema | jsonschema | Payload shape validation |
| Backend | pytest | Business logic + schema compliance |
| GTK UI | pytest + GLib | IPC message handling |
| Extension | jasmine-gjs | DBus mock responses |
| Integration | pytest | End-to-end contract adherence |

## Wayland & Flatpak Compliance

### Wayland Considerations
1. **No X11 dependencies**: All clipboard access via Wayland protocols
2. **Portal-based DBus**: Flatpak apps communicate via portals
3. **No window positioning hacks**: Use GNOME Shell chrome APIs only

### Flatpak Sandboxing

**Problem**: Flatpak apps can't directly access DBus session bus for custom services.

**Solution**: Use portal-based communication or host DBus service outside sandbox.

**Option 1: DBus Portal (Recommended)**
```xml
<!-- Flatpak manifest addition -->
<finish-args>
  <finish-arg>--talk-name=org.tfcbm.ClipboardService</finish-arg>
  <finish-arg>--own-name=org.tfcbm.ClipboardService</finish-arg>
</finish-args>
```

**Option 2: Host-side Service**
```bash
# Install DBus service system-wide (not in Flatpak)
cp org.tfcbm.ClipboardService.service /usr/share/dbus-1/services/
```

**Chosen approach**: Option 1 (portal permission) - keeps everything in Flatpak.

### GNOME Extension Communication from Flatpak

**Challenge**: Extension runs in Shell (host), app runs in Flatpak (sandbox).

**Solution**: DBus is accessible across sandbox boundary with proper permissions.

```javascript
// Extension side (runs on host)
const proxy = Gio.DBusProxy.new_sync(
    Gio.DBus.session,
    Gio.DBusProxyFlags.NONE,
    null,
    'org.tfcbm.ClipboardService',  // Flatpak exports this
    '/org/tfcbm/ClipboardService',
    'org.tfcbm.ClipboardService',
    null
);
```

```python
# Python backend (in Flatpak)
from server.src.dbus_service import TFCBMDBusService

# This works because we have --own-name permission
service = TFCBMDBusService(app, clipboard_handler=handle_clipboard)
service.start()
```

### GNOME HIG Compliance

1. **Visual Design**
   - Use libadwaita/St.Widget styling (follows system theme)
   - Proper spacing: 12px margins, 6px padding (GNOME standard)
   - Elevated surface shadow for overlay panels

2. **Interaction Patterns**
   - Overlay dismisses on `Escape` key
   - Click outside panel to dismiss (optional setting)
   - Keyboard navigation with arrow keys + Enter

3. **Accessibility**
   - Proper ARIA roles for screen readers
   - High contrast mode support
   - Keyboard-only operation

**File:** `gnome-extension/stylesheet.css`
```css
/* GNOME HIG compliant styles */
.tfcbm-sidepanel {
    background-color: rgba(36, 31, 49, 0.95); /* Shell background with transparency */
    border-radius: 0px; /* Full height panels don't need radius */
    box-shadow: 0 8px 16px rgba(0, 0, 0, 0.3); /* Elevated surface */
    padding: 0px;
    margin: 0px;
}

.tfcbm-header {
    background-color: rgba(255, 255, 255, 0.05);
    padding: 12px;
    spacing: 6px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.tfcbm-title {
    font-weight: bold;
    font-size: 14pt;
}

.tfcbm-list {
    spacing: 0px; /* Items have their own spacing */
    padding: 6px;
}

.tfcbm-item {
    padding: 12px;
    spacing: 6px;
    border-radius: 8px;
    margin: 4px 6px;
}

.tfcbm-item:hover {
    background-color: rgba(255, 255, 255, 0.08);
}

.tfcbm-item:active {
    background-color: rgba(255, 255, 255, 0.12);
}
```

## Risks & Mitigations

1. **Risk**: Extension disabled mid-session
   - **Mitigation**: GTK UI always available as fallback, graceful degradation

2. **Risk**: GNOME Shell version differences (45 vs 46 vs 47)
   - **Mitigation**: Use compatibility shims, test on all supported versions
   - **Detection**: Check `imports.misc.extensionUtils.getCurrentExtension().metadata['shell-version']`

3. **Risk**: Flatpak sandbox breaks DBus communication
   - **Mitigation**: Proper portal permissions in manifest, fallback to UNIX socket IPC

4. **Risk**: Contract drift over time
   - **Mitigation**: CI enforces contract tests on every PR

5. **Risk**: Wayland security prevents clipboard access
   - **Mitigation**: Already using GNOME extension for clipboard monitoring (works on Wayland)

## GNOME Shell Version Compatibility

**Target**: Shell 45, 46, 47 (current stable releases)

**Compatibility Strategy**:
```javascript
// gnome-extension/compatibility.js
const Config = imports.misc.config;
const [major, minor] = Config.PACKAGE_VERSION.split('.').map(Number);

const Compat = {
    // Shell 45 changed addChrome API
    addChrome(actor, params) {
        if (major >= 45) {
            Main.layoutManager.addChrome(actor, params);
        } else {
            // Old API for Shell 44 and below
            Main.layoutManager.addChrome(actor);
        }
    },

    // Shell 46 changed DBus proxy creation
    makeProxy(iface, name, path) {
        if (major >= 46) {
            return Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SESSION,
                Gio.DBusProxyFlags.NONE,
                Gio.DBusInterfaceInfo.new_for_xml(iface),
                name,
                path,
                name,
                null
            );
        } else {
            // Old makeProxyWrapper API
            const Proxy = Gio.DBusProxy.makeProxyWrapper(iface);
            return new Proxy(Gio.DBus.session, name, path);
        }
    }
};
```

**metadata.json**:
```json
{
  "shell-version": ["45", "46", "47"],
  "uuid": "tfcbm-clipboard-monitor@github.com",
  "name": "TFCBM Clipboard Monitor",
  "description": "Advanced clipboard manager with side panel UI",
  "url": "https://github.com/yourrepo/tfcbm"
}
```

## Implementation Details

### Phase 1: Contract Infrastructure (Week 1)

#### 1.1 JSON Schema Definition

**File:** `server/src/contracts/ipc_contract_v1.json`
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://tfcbm.github.io/schemas/ipc-v1.json",
  "title": "TFCBM IPC Contract v1.0.0",
  "version": "1.0.0",

  "definitions": {
    "timestamp": {
      "type": "string",
      "format": "date-time",
      "description": "ISO 8601 timestamp"
    },

    "item_type": {
      "enum": ["text", "url", "image/png", "image/jpeg", "image/screenshot", "file"],
      "description": "Type of clipboard item"
    },

    "clipboard_item": {
      "type": "object",
      "required": ["id", "type", "timestamp"],
      "properties": {
        "id": {
          "type": "integer",
          "minimum": 1,
          "description": "Unique item ID"
        },
        "type": {
          "$ref": "#/definitions/item_type"
        },
        "content": {
          "type": ["string", "null"],
          "description": "Text content or null for binary items"
        },
        "thumbnail": {
          "type": ["string", "null"],
          "description": "Base64 encoded thumbnail for images"
        },
        "timestamp": {
          "$ref": "#/definitions/timestamp"
        },
        "is_favorite": {
          "type": "boolean",
          "default": false
        },
        "is_secret": {
          "type": "boolean",
          "default": false
        },
        "tags": {
          "type": "array",
          "items": { "type": "string" },
          "default": []
        }
      }
    }
  },

  "messages": {
    "get_history": {
      "request": {
        "type": "object",
        "required": ["action"],
        "properties": {
          "action": { "const": "get_history" },
          "offset": { "type": "integer", "minimum": 0, "default": 0 },
          "limit": { "type": "integer", "minimum": 1, "maximum": 100, "default": 20 },
          "filters": {
            "type": "array",
            "items": { "$ref": "#/definitions/item_type" },
            "default": []
          }
        }
      },
      "response": {
        "type": "object",
        "required": ["type", "items", "total_count", "offset"],
        "properties": {
          "type": { "const": "history" },
          "items": {
            "type": "array",
            "items": { "$ref": "#/definitions/clipboard_item" }
          },
          "total_count": { "type": "integer", "minimum": 0 },
          "offset": { "type": "integer", "minimum": 0 }
        }
      }
    },

    "new_item": {
      "signal": {
        "type": "object",
        "required": ["type", "item"],
        "properties": {
          "type": { "const": "new_item" },
          "item": { "$ref": "#/definitions/clipboard_item" }
        }
      }
    },

    "get_ui_mode": {
      "request": {
        "type": "object",
        "required": ["action"],
        "properties": {
          "action": { "const": "get_ui_mode" }
        }
      },
      "response": {
        "type": "object",
        "required": ["type", "mode", "alignment"],
        "properties": {
          "type": { "const": "ui_mode" },
          "mode": { "enum": ["windowed", "sidepanel"] },
          "alignment": { "enum": ["left", "right", "none"] }
        }
      }
    },

    "set_ui_mode": {
      "request": {
        "type": "object",
        "required": ["action", "mode"],
        "properties": {
          "action": { "const": "set_ui_mode" },
          "mode": { "enum": ["windowed", "sidepanel"] },
          "alignment": { "enum": ["left", "right"], "default": "right" }
        }
      },
      "response": {
        "type": "object",
        "required": ["type", "success"],
        "properties": {
          "type": { "const": "ui_mode_updated" },
          "success": { "type": "boolean" }
        }
      }
    }
  }
}
```

#### 1.2 Contract Validator

**File:** `server/src/contracts/validator.py`
```python
import json
from pathlib import Path
from jsonschema import validate, ValidationError, Draft7Validator

class ContractValidator:
    """Validates IPC messages against the contract schema"""

    def __init__(self, schema_path: str = None):
        if schema_path is None:
            schema_path = Path(__file__).parent / "ipc_contract_v1.json"

        with open(schema_path) as f:
            self.schema = json.load(f)

        self.validator = Draft7Validator(self.schema)

    def validate_request(self, message_type: str, data: dict):
        """Validate a request message"""
        schema = self.schema['messages'][message_type]['request']
        try:
            validate(data, schema)
            return True, None
        except ValidationError as e:
            return False, str(e)

    def validate_response(self, message_type: str, data: dict):
        """Validate a response message"""
        schema = self.schema['messages'][message_type]['response']
        try:
            validate(data, schema)
            return True, None
        except ValidationError as e:
            return False, str(e)

    def validate_signal(self, signal_type: str, data: dict):
        """Validate a signal/broadcast message"""
        schema = self.schema['messages'][signal_type]['signal']
        try:
            validate(data, schema)
            return True, None
        except ValidationError as e:
            return False, str(e)
```

#### 1.3 Backend Contract Tests

**File:** `server/test/contract/test_ipc_messages.py`
```python
import pytest
from server.src.contracts.validator import ContractValidator
from server.src.services.ipc_service import IPCService

@pytest.fixture
def validator():
    return ContractValidator()

@pytest.fixture
def ipc_service(database_service, settings_service, clipboard_service):
    return IPCService(database_service, settings_service, clipboard_service)

class TestGetHistoryContract:
    def test_request_minimal(self, validator):
        """Minimal valid get_history request"""
        request = {"action": "get_history"}
        valid, error = validator.validate_request("get_history", request)
        assert valid, f"Validation failed: {error}"

    def test_request_with_pagination(self, validator):
        """get_history with pagination parameters"""
        request = {
            "action": "get_history",
            "offset": 20,
            "limit": 50
        }
        valid, error = validator.validate_request("get_history", request)
        assert valid, f"Validation failed: {error}"

    def test_request_invalid_limit(self, validator):
        """get_history with invalid limit should fail"""
        request = {
            "action": "get_history",
            "limit": 200  # Exceeds maximum of 100
        }
        valid, error = validator.validate_request("get_history", request)
        assert not valid

    def test_response_shape(self, validator, ipc_service):
        """Backend response matches contract"""
        # Simulate IPC request handling
        request = {"action": "get_history", "limit": 5}
        response = ipc_service._prepare_history_response(
            offset=0,
            limit=5,
            items=[],
            total=0
        )

        valid, error = validator.validate_response("get_history", response)
        assert valid, f"Response validation failed: {error}"
        assert response['type'] == 'history'
        assert 'items' in response
        assert 'total_count' in response

class TestNewItemSignal:
    def test_new_item_signal_text(self, validator):
        """new_item signal for text clipboard item"""
        signal = {
            "type": "new_item",
            "item": {
                "id": 42,
                "type": "text",
                "content": "Hello world",
                "timestamp": "2024-01-15T10:30:00Z",
                "is_favorite": False,
                "is_secret": False,
                "tags": []
            }
        }
        valid, error = validator.validate_signal("new_item", signal)
        assert valid, f"Signal validation failed: {error}"

    def test_new_item_signal_image(self, validator):
        """new_item signal for image with thumbnail"""
        signal = {
            "type": "new_item",
            "item": {
                "id": 43,
                "type": "image/png",
                "content": None,
                "thumbnail": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
                "timestamp": "2024-01-15T10:31:00Z"
            }
        }
        valid, error = validator.validate_signal("new_item", signal)
        assert valid, f"Signal validation failed: {error}"

class TestUIModeContract:
    def test_set_ui_mode_sidepanel(self, validator):
        """Switch to sidepanel mode"""
        request = {
            "action": "set_ui_mode",
            "mode": "sidepanel",
            "alignment": "right"
        }
        valid, error = validator.validate_request("set_ui_mode", request)
        assert valid, f"Request validation failed: {error}"

    def test_get_ui_mode_response(self, validator):
        """UI mode query response"""
        response = {
            "type": "ui_mode",
            "mode": "windowed",
            "alignment": "none"
        }
        valid, error = validator.validate_response("get_ui_mode", response)
        assert valid, f"Response validation failed: {error}"
```

#### 1.4 CI Integration

**File:** `.github/workflows/contract-tests.yml`
```yaml
name: Contract Tests

on: [push, pull_request]

jobs:
  contract-validation:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install jsonschema pytest
          pip install -r requirements.txt

      - name: Validate contract schema
        run: |
          python -m jsonschema \
            -i server/src/contracts/ipc_contract_v1.json \
            http://json-schema.org/draft-07/schema

      - name: Run contract tests
        run: |
          pytest server/test/contract/ -v --tb=short

      - name: Check for contract changes
        run: |
          # Fail if contract changed without version bump
          git diff --exit-code server/src/contracts/ipc_contract_v1.json || \
          (echo "Contract changed! Did you bump the version?" && exit 1)
```

## Success Criteria

### Phase 1 (Contract Foundation)
- [x] JSON schema defined with version 1.0.0
- [ ] Contract validator implemented and tested
- [ ] Backend IPC service passes all contract tests
- [ ] CI enforces contract validation on every commit
- [ ] Documentation for adding new messages to contract

### Phase 2 (UI Mode Settings)
- [ ] Settings page has UI mode selector (windowed/sidepanel)
- [ ] Sidepanel mode shows alignment options (left/right) with icons
- [ ] Backend stores UI mode preference in settings.json
- [ ] IPC service handles get_ui_mode and set_ui_mode actions
- [ ] GTK UI reacts to mode changes (hide window when sidepanel active)

### Phase 3 (Extension Side Panel)
- [ ] Extension can read UI mode from backend
- [ ] Side panel renders with proper GNOME HIG styling
- [ ] Panel loads clipboard history from DBus/IPC
- [ ] Items are clickable and copy to clipboard
- [ ] Panel shows/hides with smooth animation
- [ ] Search functionality works
- [ ] Keyboard navigation (arrow keys, Enter, Escape)

### Phase 4 (Integration & Polish)
- [ ] Both GTK and extension UIs receive identical data
- [ ] Mode switching works seamlessly (no restart required)
- [ ] Flatpak build includes proper DBus permissions
- [ ] Extension works on Shell 45, 46, 47
- [ ] Wayland-only testing (no X11 fallback)
- [ ] Accessibility: screen reader support, keyboard-only
- [ ] Performance: panel opens in <100ms, smooth scrolling

### Quality Gates
- [ ] No TypeErrors in extension logs
- [ ] No schema validation errors in backend logs
- [ ] Contract tests pass on CI
- [ ] Extension passes GNOME review guidelines
- [ ] Flatpak passes flathub quality checks

## Timeline

### Week 1: Contract Foundation
- **Day 1-2**: JSON schema + validator implementation
- **Day 3-4**: Backend contract tests + CI integration
- **Day 5**: Documentation + schema versioning strategy

### Week 2: Settings & Backend Support
- **Day 1-2**: UI mode settings page (GTK)
- **Day 3**: Backend IPC handlers for UI mode
- **Day 4**: GTK UI responds to mode changes
- **Day 5**: Testing + bug fixes

### Week 3: Extension Side Panel (Basic)
- **Day 1-2**: Extension panel structure + styling
- **Day 3**: DBus client + history loading
- **Day 4**: Item rendering + click handlers
- **Day 5**: Show/hide animations + keyboard shortcuts

### Week 4: Integration & Polish
- **Day 1**: Cross-UI contract validation tests
- **Day 2**: Flatpak permissions + DBus portal setup
- **Day 3**: GNOME Shell 45/46/47 compatibility testing
- **Day 4**: Accessibility + keyboard navigation
- **Day 5**: Performance optimization + final QA

**Total: 4 weeks for production-ready MVP**

## Maintenance & Evolution

### Adding New Messages to Contract

1. **Update schema** with new message definition
2. **Bump version** (patch for additions, major for breaking changes)
3. **Write contract tests** for new message
4. **Implement in backend** with validation
5. **Update extension** to use new message (if applicable)
6. **Run CI** to ensure no regressions

### Deprecation Process

1. **Mark field as deprecated** in schema comments
2. **Add migration guide** in CHANGELOG.md
3. **Support for 2 minor versions** (e.g., 1.1 → 1.2 → 1.3)
4. **Remove in next major** (e.g., 2.0)

Example:
```json
{
  "old_field": {
    "type": "string",
    "deprecated": true,
    "description": "DEPRECATED: Use new_field instead. Will be removed in v2.0"
  },
  "new_field": {
    "type": "string",
    "description": "Replacement for old_field"
  }
}
```

## Next Steps

**To begin implementation:**

1. **Review this plan** - confirm approach aligns with your vision
2. **Start Phase 1** - implement JSON schema + contract tests
3. **Iterate** - adjust based on learnings from contract testing

**Decisions:**
- ✅ True overlay side panel (doesn't resize windows)
- ✅ Wayland/Flatpak/GNOME compliant
- ✅ **Extension bundled with Flatpak** (not separate install)
- ✅ **SOLID/TDD/Clean Code** - clarity over cleverness
- ✅ **Must be testable via flatpak install at every stage**
- ✅ **Defer search to Phase 2** - MVP is basic list + click-to-copy
- ✅ **Structured logging** - see [`LOGGING_STRATEGY.md`](./LOGGING_STRATEGY.md)

## Development Workflow (Flatpak-First)

Since the app ONLY runs as Flatpak, every commit must be installable:

```bash
# Build and install locally
flatpak-builder --user --install --force-clean build io.github.dyslechtchitect.tfcbm.yml

# Run to test
flatpak run io.github.dyslechtchitect.tfcbm

# View logs in real-time
journalctl --user -f -t io.github.dyslechtchitect.tfcbm
```

**Each phase deliverable:**
- Phase 1: Contract tests pass inside Flatpak
- Phase 2: Settings UI works via Flatpak install
- Phase 3: Extension bundled and functional
- Phase 4: Production-ready Flatpak build

Ready to start coding when you give the green light! 🚀
