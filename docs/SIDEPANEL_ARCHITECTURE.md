# Side Panel Architecture Design

## Design Principles

- **SOLID**: Single responsibility, dependency injection, interface segregation
- **Clean Architecture**: Hexagonal architecture with ports and adapters
- **Clarity over Cleverness**: Obvious intent, no magic
- **Testable**: All components injectable and mockable

## Component Structure

```
gnome-extension/
├── src/
│   ├── domain/
│   │   └── SidePanelPort.js          # Port: Abstract interface for side panel operations
│   ├── adapters/
│   │   ├── DBusIPCClient.js          # Adapter: IPC client to fetch clipboard items from backend
│   │   └── GnomeSidePanel.js         # Adapter: GNOME Shell side panel UI implementation
│   └── SidePanelManager.js           # Service: Manages side panel lifecycle and state
└── extension.js                      # Updated to integrate side panel manager
```

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      Extension.js                                │
│  - Lifecycle management (enable/disable)                         │
│  - Checks UI mode from backend via DBus                          │
│  - Routes toggle action to SidePanelManager or WindowActivation  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ├──────────────────────────────┐
                              │                              │
                              ▼                              ▼
                    ┌──────────────────────┐      ┌──────────────────────┐
                    │ SidePanelManager     │      │ Window Activation    │
                    │  (Service)           │      │  (Existing DBus)     │
                    └──────────────────────┘      └──────────────────────┘
                              │
                ┌─────────────┼─────────────┐
                │                            │
                ▼                            ▼
      ┌──────────────────┐        ┌──────────────────┐
      │ DBusIPCClient    │        │ GnomeSidePanel   │
      │  (Adapter)       │        │  (Adapter)       │
      │                  │        │                  │
      │ - Connects to    │        │ - St.BoxLayout   │
      │   backend IPC    │        │ - Slide-in anim  │
      │ - get_history    │        │ - Item rendering │
      │ - Listens for    │        │ - Keyboard nav   │
      │   new_item       │        │                  │
      └──────────────────┘        └──────────────────┘
                │                            │
                └────────────────┬───────────┘
                                 │
                                 ▼
                      ┌──────────────────────┐
                      │ SidePanelPort        │
                      │  (Domain Interface)  │
                      │                      │
                      │ - show()             │
                      │ - hide()             │
                      │ - addItem(item)      │
                      │ - clearItems()       │
                      └──────────────────────┘
```

## Component Responsibilities

### 1. SidePanelPort (Domain Interface)

**Purpose**: Abstract interface defining side panel operations

**Methods**:
```javascript
export class SidePanelPort {
    show() { throw new Error('Not implemented'); }
    hide() { throw new Error('Not implemented'); }
    addItem(item) { throw new Error('Not implemented'); }
    clearItems() { throw new Error('Not implemented'); }
    isVisible() { throw new Error('Not implemented'); }
}
```

**Why**: Allows different UI implementations (e.g., GNOME 45 vs 47, testing fakes)

### 2. DBusIPCClient (Adapter)

**Purpose**: Communicates with TFCBM backend via IPC to fetch clipboard items

**Responsibilities**:
- Connect to backend IPC socket (same as GTK UI)
- Send `get_history` requests
- Listen for `new_item` broadcasts
- Parse JSON responses

**Dependencies**:
- Gio.SocketClient for IPC connection
- JSON parsing

**Why**: Backend already has IPC handlers - reuse them instead of duplicating logic

### 3. GnomeSidePanel (Adapter)

**Purpose**: Renders side panel UI using GNOME Shell toolkit (St)

**Responsibilities**:
- Create St.BoxLayout container
- Position on left/right edge based on alignment setting
- Slide-in/out animation using Clutter.Actor.ease()
- Render clipboard items as St.Button widgets
- Handle keyboard navigation (arrows, Escape)
- Handle item click → copy to clipboard

**Styling**:
- Match GNOME Shell theme
- Blur background (like notification panel)
- Rounded corners on opposite edge
- Scrollable item list

**Animation**:
```javascript
// Slide in from right
panel.translation_x = panel.width; // Start off-screen
panel.ease({
    translation_x: 0,
    duration: 250,
    mode: Clutter.AnimationMode.EASE_OUT_QUAD
});
```

**Why**: Native GNOME Shell look and feel, smooth performance

### 4. SidePanelManager (Service)

**Purpose**: Orchestrates side panel lifecycle and state

**Responsibilities**:
- Check UI mode from backend on startup
- Show/hide panel based on keyboard shortcut or tray icon click
- Fetch initial history from backend
- Listen for new items and update panel
- Handle panel destruction on disable

**State**:
- `_isVisible`: boolean
- `_alignment`: 'left' | 'right'
- `_items`: array of clipboard items

**Methods**:
```javascript
class SidePanelManager {
    constructor(ipcClient, sidePanel, settings) {
        this._ipcClient = ipcClient;      // DBusIPCClient
        this._sidePanel = sidePanel;      // GnomeSidePanel
        this._settings = settings;        // Extension settings
    }

    async initialize() {
        // Fetch UI mode and alignment from backend
        // Load initial history
        // Set up new_item listener
    }

    toggle() {
        if (this._sidePanel.isVisible()) {
            this._sidePanel.hide();
        } else {
            this._sidePanel.show();
        }
    }

    destroy() {
        // Clean up IPC connection
        // Destroy panel UI
    }
}
```

**Why**: Single responsibility - manages panel lifecycle, delegates rendering to adapter

### 5. Extension.js Updates

**Changes**:
1. Add DBus method `GetUIMode()` to fetch UI mode from backend
2. On `enable()`, check UI mode:
   - If `sidepanel`: Create `SidePanelManager`
   - If `windowed`: Use existing window activation
3. On `_toggleUI()`, route to panel or window based on mode
4. Listen for `ui_mode_changed` signal to switch between modes dynamically

**Why**: Extension knows which UI to show based on user preference

## Data Flow

### Startup Flow

```
1. Extension enables
2. Extension calls backend DBus: GetUIMode()
3. Backend returns: {mode: 'sidepanel', alignment: 'right'}
4. Extension creates SidePanelManager
5. SidePanelManager connects to IPC
6. SidePanelManager sends: {action: 'get_history', limit: 20}
7. Backend responds: {type: 'history', items: [...]}
8. SidePanelManager calls sidePanel.addItem() for each item
9. Panel is ready (hidden until toggled)
```

### Toggle Flow

```
1. User presses keyboard shortcut (Ctrl+Escape)
2. Extension calls sidePanelManager.toggle()
3. SidePanelManager calls sidePanel.show()
4. GnomeSidePanel animates in from right edge
5. User sees clipboard items
6. User presses Escape
7. SidePanelManager calls sidePanel.hide()
8. GnomeSidePanel animates out
```

### New Item Flow

```
1. User copies text
2. Backend detects clipboard change
3. Backend broadcasts via IPC: {type: 'new_item', item: {...}}
4. DBusIPCClient receives broadcast
5. DBusIPCClient notifies SidePanelManager
6. SidePanelManager calls sidePanel.addItem(item)
7. GnomeSidePanel prepends item to top of list
8. If panel is visible, user sees new item appear
```

## IPC Protocol

Side panel uses same IPC protocol as GTK UI (already implemented in Phase 2):

**Connect**: UNIX socket at `$XDG_RUNTIME_DIR/tfcbm-ipc.sock`

**Request (get_history)**:
```json
{"action": "get_history", "limit": 20, "offset": 0}
```

**Response**:
```json
{
    "type": "history",
    "items": [
        {"id": 1, "type": "text", "content": "...", "timestamp": "..."},
        ...
    ],
    "total_count": 250
}
```

**Broadcast (new_item)**:
```json
{
    "type": "new_item",
    "item": {"id": 251, "type": "text", "content": "...", "timestamp": "..."}
}
```

## UI Specifications

### Panel Dimensions

- Width: 400px (configurable in future)
- Height: Full screen height
- Position: Anchored to left or right edge
- Z-index: Above all windows, below lock screen

### Item Rendering

Each item displayed as:
```
┌─────────────────────────────────────────┐
│ [Icon] Text preview...           [Time] │  ← St.Button
│        (truncated to 2 lines)            │
└─────────────────────────────────────────┘
```

- Icon based on type (text, image, file)
- Preview text truncated with ellipsis
- Timestamp formatted as relative time ("2m ago")
- Hover effect: highlight
- Click: copy item to clipboard + hide panel

### Keyboard Navigation

- **Escape**: Hide panel
- **Up/Down arrows**: Navigate items
- **Enter**: Copy selected item
- **Tab**: Focus search box (future)

### Accessibility

- Proper ARIA labels
- Screen reader support via St.Label
- High contrast theme support

## Testing Strategy

### Unit Tests

**SidePanelManager.test.js**:
```javascript
describe('SidePanelManager', () => {
    it('should show panel when toggled', async () => {
        const fakeIPC = new FakeIPCClient();
        const fakePanel = new FakeSidePanel();
        const manager = new SidePanelManager(fakeIPC, fakePanel);

        manager.toggle();

        expect(fakePanel.isVisible()).toBe(true);
    });
});
```

**GnomeSidePanel.test.js**:
- Test panel creation
- Test slide-in animation
- Test item rendering
- Test keyboard navigation

**DBusIPCClient.test.js**:
- Test IPC connection
- Test get_history request/response
- Test new_item broadcast handling

### Integration Testing

- Manual testing in GNOME Shell 47
- Test with different alignments (left/right)
- Test mode switching (windowed ↔ sidepanel)
- Test with large item counts (100+ items)

### E2E Testing

1. Copy text → Verify appears in panel
2. Click item → Verify copied to clipboard
3. Keyboard shortcut → Verify panel toggles
4. Escape key → Verify panel hides

## Implementation Phases

### Phase 3.1: Backend DBus Method (TDD)

- [ ] Add `GetUIMode()` method to DBus service
- [ ] Write tests for DBus method
- [ ] Verify returns correct mode from settings

### Phase 3.2: IPC Client (TDD)

- [ ] Create DBusIPCClient class
- [ ] Write tests with fake socket
- [ ] Implement get_history request
- [ ] Implement new_item listener

### Phase 3.3: Side Panel UI (Incremental)

- [ ] Create GnomeSidePanel class
- [ ] Implement basic panel with 1 test item
- [ ] Add slide-in animation
- [ ] Add item rendering from real data
- [ ] Add keyboard navigation

### Phase 3.4: Integration

- [ ] Create SidePanelManager
- [ ] Update extension.js to check mode
- [ ] Test toggling between modes
- [ ] Test real-world usage

## Success Criteria

✅ Side panel slides in smoothly (250ms animation)
✅ Panel displays clipboard items from backend
✅ Clicking item copies to clipboard
✅ Keyboard shortcut toggles panel
✅ Escape key hides panel
✅ New items appear in real-time
✅ Mode switching works without restart
✅ No memory leaks on enable/disable cycles
✅ Follows GNOME HIG for panels

## Non-Goals (Future Work)

- Search/filter in side panel (Phase 4)
- Settings UI in side panel (Phase 4)
- Multi-monitor support (Phase 4)
- Touch gesture support (Phase 4)

---

**Ready to implement Phase 3.1: Backend DBus Method** 🚀
