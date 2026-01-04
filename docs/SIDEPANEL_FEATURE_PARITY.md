# Side Panel Feature Parity Plan

## Goal
Add all major GTK UI features to the GNOME extension side panel using contract-driven development.

## Status Check

### ✅ Already Completed (Phase 1-4 from SIDEPANEL_PLAN.md)
- [x] Contract schema defined (`server/src/contracts/ipc_contract_v1.json`)
- [x] Contract validator implemented (`server/src/contracts/validator.py`)
- [x] Backend IPC service with get_history support
- [x] UI mode settings (windowed/sidepanel toggle)
- [x] Extension side panel with basic list view
- [x] IPC connection working (UNIX socket)
- [x] Items display with icon, preview text, timestamp
- [x] Click to copy functionality
- [x] Smooth slide-in/out animations
- [x] Keyboard shortcut (Shift+Super+V)
- [x] Tray icon integration

### Current GTK UI Features to Add to Side Panel

Based on `ui/windows/clipboard_window.py` and managers:

1. **Search** - SearchManager
2. **Filtering** - FilterBarManager (by type: text, images, files, URLs)
3. **Sorting** - SortManager (newest first, oldest first, recently pasted)
4. **Tags** - TagDialogManager, UserTagsManager, TagFilterManager
5. **Favorites** - Toggle favorite status
6. **Delete items** - Delete individual items or clear all
7. **Secrets** - View/hide secret items (password-protected)
8. **Pagination** - Load more items on scroll
9. **Image thumbnails** - Display image previews
10. **Multi-select** - Select multiple items for batch operations

## Implementation Plan: Contract-First Development

### Phase 5: Search & Filtering (Week 1)

#### Contract Updates

**File:** `server/src/contracts/ipc_contract_v1.json`

Add to messages:
```json
{
  "search": {
    "request": {
      "type": "object",
      "required": ["action"],
      "properties": {
        "action": { "const": "search" },
        "query": { "type": "string" },
        "filters": {
          "type": "object",
          "properties": {
            "types": {
              "type": "array",
              "items": { "enum": ["text", "url", "image/png", "image/jpeg", "file"] }
            },
            "is_favorite": { "type": "boolean" },
            "tags": { "type": "array", "items": { "type": "string" } }
          }
        },
        "limit": { "type": "integer", "minimum": 1, "maximum": 100, "default": 20 },
        "offset": { "type": "integer", "minimum": 0, "default": 0 }
      }
    },
    "response": {
      "type": "object",
      "required": ["type", "items", "total_count"],
      "properties": {
        "type": { "const": "search_results" },
        "items": {
          "type": "array",
          "items": { "$ref": "#/definitions/clipboard_item" }
        },
        "total_count": { "type": "integer", "minimum": 0 }
      }
    }
  }
}
```

#### Backend Tests

**File:** `server/test/contract/test_search_contract.py`
```python
def test_search_request_minimal(validator):
    """Minimal search request with just query"""
    request = {
        "action": "search",
        "query": "hello"
    }
    valid, error = validator.validate_request("search", request)
    assert valid

def test_search_with_filters(validator):
    """Search with type filters"""
    request = {
        "action": "search",
        "query": "test",
        "filters": {
            "types": ["text", "url"],
            "is_favorite": True
        }
    }
    valid, error = validator.validate_request("search", request)
    assert valid

def test_search_response(validator, ipc_service):
    """Search response matches contract"""
    response = ipc_service._handle_search({
        "action": "search",
        "query": "test"
    })
    valid, error = validator.validate_response("search", response)
    assert valid
```

#### Extension UI

**File:** `gnome-extension/src/adapters/GnomeSidePanel.js`

Add search bar to panel:
```javascript
_buildHeader() {
    const header = new St.BoxLayout({
        style_class: 'tfcbm-header',
        vertical: true
    });

    // Title row
    const titleRow = new St.BoxLayout({ vertical: false });
    const title = new St.Label({ text: 'Clipboard History' });
    titleRow.add_child(title);
    header.add_child(titleRow);

    // Search bar
    this._searchEntry = new St.Entry({
        style_class: 'tfcbm-search-entry',
        hint_text: 'Search clipboard...',
        can_focus: true,
        x_expand: true
    });

    this._searchEntry.clutter_text.connect('text-changed', () => {
        const query = this._searchEntry.get_text();
        this._onSearchChanged(query);
    });

    header.add_child(this._searchEntry);

    // Filter buttons
    const filterRow = new St.BoxLayout({
        style_class: 'tfcbm-filter-row',
        x_expand: true
    });

    this._filterButtons = {
        'text': this._createFilterButton('Text', 'text-x-generic-symbolic'),
        'image': this._createFilterButton('Images', 'image-x-generic-symbolic'),
        'file': this._createFilterButton('Files', 'document-open-symbolic'),
        'url': this._createFilterButton('URLs', 'web-browser-symbolic')
    };

    Object.values(this._filterButtons).forEach(btn => filterRow.add_child(btn));
    header.add_child(filterRow);

    return header;
}

_createFilterButton(label, icon) {
    const btn = new St.Button({
        style_class: 'tfcbm-filter-button',
        toggle_mode: true,
        child: new St.Icon({ icon_name: icon, icon_size: 16 })
    });
    btn.connect('toggled', () => this._onFiltersChanged());
    return btn;
}

_onSearchChanged(query) {
    // Debounce search
    if (this._searchTimeout) {
        GLib.source_remove(this._searchTimeout);
    }

    this._searchTimeout = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 300, () => {
        this._performSearch(query);
        this._searchTimeout = null;
        return GLib.SOURCE_REMOVE;
    });
}

async _performSearch(query) {
    const filters = this._getActiveFilters();
    await this._ipcClient.search(query, filters);
}

_getActiveFilters() {
    const types = [];
    if (this._filterButtons['text'].get_checked()) types.push('text');
    if (this._filterButtons['image'].get_checked()) types.push('image/png', 'image/jpeg');
    if (this._filterButtons('file'].get_checked()) types.push('file');
    if (this._filterButtons['url'].get_checked()) types.push('url');

    return { types };
}
```

**File:** `gnome-extension/src/adapters/IPCClient.js`

Add search method:
```javascript
async search(query, filters = {}, limit = 20, offset = 0) {
    return this.send({
        action: 'search',
        query,
        filters,
        limit,
        offset
    });
}
```

#### Integration

1. Update IPC service handler for search action
2. Add search tests to backend
3. Add search UI to extension
4. Test contract compliance end-to-end

---

### Phase 6: Tags (Week 2)

#### Contract Updates

Add tag-related messages:
```json
{
  "get_tags": {
    "request": {
      "action": { "const": "get_tags" }
    },
    "response": {
      "type": "object",
      "required": ["type", "tags"],
      "properties": {
        "type": { "const": "tags" },
        "tags": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "id": { "type": "integer" },
              "name": { "type": "string" },
              "color": { "type": "string" }
            }
          }
        }
      }
    }
  },

  "add_tag": {
    "request": {
      "action": { "const": "add_tag" },
      "item_id": { "type": "integer" },
      "tag_id": { "type": "integer" }
    },
    "response": {
      "type": { "const": "tag_added" },
      "success": { "type": "boolean" }
    }
  },

  "remove_tag": {
    "request": {
      "action": { "const": "remove_tag" },
      "item_id": { "type": "integer" },
      "tag_id": { "type": "integer" }
    },
    "response": {
      "type": { "const": "tag_removed" },
      "success": { "type": "boolean" }
    }
  }
}
```

#### Extension UI

Add tag display to items:
```javascript
_renderItemTags(item) {
    if (!item.tags || item.tags.length === 0) return null;

    const tagsBox = new St.BoxLayout({
        style_class: 'tfcbm-tags-box',
        vertical: false,
        style: 'spacing: 4px;'
    });

    item.tags.forEach(tag => {
        const tagLabel = new St.Label({
            text: tag.name,
            style_class: 'tfcbm-tag',
            style: `background-color: ${tag.color}; padding: 2px 6px; border-radius: 4px;`
        });
        tagsBox.add_child(tagLabel);
    });

    return tagsBox;
}
```

Add tag management dialog:
```javascript
class TagDialog {
    constructor(item, availableTags) {
        this._item = item;
        this._availableTags = availableTags;
        this._buildUI();
    }

    _buildUI() {
        this._dialog = new St.BoxLayout({
            style_class: 'tfcbm-tag-dialog',
            vertical: true,
            reactive: true
        });

        // Title
        const title = new St.Label({ text: 'Manage Tags' });
        this._dialog.add_child(title);

        // Tag list
        this._availableTags.forEach(tag => {
            const tagRow = this._createTagRow(tag);
            this._dialog.add_child(tagRow);
        });

        Main.uiGroup.add_child(this._dialog);
    }

    _createTagRow(tag) {
        const row = new St.BoxLayout({ vertical: false });

        const checkbox = new St.Button({
            style_class: 'tfcbm-tag-checkbox',
            toggle_mode: true,
            checked: this._item.tags.some(t => t.id === tag.id)
        });

        checkbox.connect('toggled', () => {
            if (checkbox.get_checked()) {
                this._onTagAdded(tag);
            } else {
                this._onTagRemoved(tag);
            }
        });

        const label = new St.Label({ text: tag.name });

        row.add_child(checkbox);
        row.add_child(label);

        return row;
    }
}
```

---

### Phase 7: Favorites & Delete (Week 3)

#### Contract Updates

```json
{
  "toggle_favorite": {
    "request": {
      "action": { "const": "toggle_favorite" },
      "item_id": { "type": "integer" }
    },
    "response": {
      "type": { "const": "favorite_toggled" },
      "item_id": { "type": "integer" },
      "is_favorite": { "type": "boolean" }
    }
  },

  "delete_item": {
    "request": {
      "action": { "const": "delete_item" },
      "item_id": { "type": "integer" }
    },
    "response": {
      "type": { "const": "item_deleted" },
      "success": { "type": "boolean" }
    }
  }
}
```

#### Extension UI

Add action buttons to items:
```javascript
_buildItemActions(item) {
    const actionsBox = new St.BoxLayout({
        style_class: 'tfcbm-item-actions',
        vertical: false,
        style: 'spacing: 4px;'
    });

    // Favorite button
    const favoriteBtn = new St.Button({
        style_class: 'tfcbm-action-btn',
        child: new St.Icon({
            icon_name: item.is_favorite ? 'starred-symbolic' : 'non-starred-symbolic',
            icon_size: 16
        })
    });
    favoriteBtn.connect('clicked', () => this._onToggleFavorite(item));

    // Delete button
    const deleteBtn = new St.Button({
        style_class: 'tfcbm-action-btn tfcbm-danger',
        child: new St.Icon({
            icon_name: 'user-trash-symbolic',
            icon_size: 16
        })
    });
    deleteBtn.connect('clicked', () => this._onDeleteItem(item));

    actionsBox.add_child(favoriteBtn);
    actionsBox.add_child(deleteBtn);

    return actionsBox;
}

async _onToggleFavorite(item) {
    await this._ipcClient.send({
        action: 'toggle_favorite',
        item_id: item.id
    });
}

async _onDeleteItem(item) {
    // Show confirmation
    const confirmed = await this._showConfirmDialog('Delete this item?');
    if (confirmed) {
        await this._ipcClient.send({
            action: 'delete_item',
            item_id: item.id
        });
    }
}
```

---

### Phase 8: Pagination & Image Thumbnails (Week 4)

#### Image Thumbnails

Update contract to include thumbnail in clipboard_item:
```json
{
  "thumbnail": {
    "type": ["string", "null"],
    "description": "Base64 encoded thumbnail (max 100x100px)"
  }
}
```

Extension rendering:
```javascript
_renderItemPreview(item) {
    if (item.type.startsWith('image/') && item.thumbnail) {
        // Display image thumbnail
        const imageTexture = St.TextureCache.get_default().load_image_from_data(
            GLib.Bytes.new(GLib.base64_decode(item.thumbnail)),
            -1, -1
        );

        const image = new St.Icon({
            gicon: imageTexture,
            icon_size: 64
        });

        return image;
    } else {
        // Display text preview
        return new St.Label({
            text: this._getPreviewText(item),
            style: 'font-size: 14px;'
        });
    }
}
```

#### Infinite Scroll Pagination

```javascript
_buildScrollView() {
    this.scrollView = new St.ScrollView({
        style_class: 'tfcbm-scroll-view',
        hscrollbar_policy: St.PolicyType.NEVER,
        vscrollbar_policy: St.PolicyType.AUTOMATIC
    });

    // Connect scroll event
    const vAdjust = this.scrollView.get_vscroll_bar().get_adjustment();
    vAdjust.connect('changed', () => this._onScrollChanged(vAdjust));

    this._itemsContainer = new St.BoxLayout({
        vertical: true,
        style: 'spacing: 8px;'
    });

    this.scrollView.add_child(this._itemsContainer);
}

_onScrollChanged(adjustment) {
    const value = adjustment.get_value();
    const upper = adjustment.get_upper();
    const pageSize = adjustment.get_page_size();

    // Load more when 80% scrolled
    if (value + pageSize >= upper * 0.8 && !this._loading) {
        this._loadMore();
    }
}

async _loadMore() {
    if (this._loading || !this._hasMore) return;

    this._loading = true;
    this._offset += this._limit;

    await this._ipcClient.getHistory(this._limit, this._offset);

    this._loading = false;
}
```

---

## Testing Strategy

### 1. Contract Tests (Python)

For each new message type:
```python
# server/test/contract/test_<feature>_contract.py

def test_<action>_request_schema(validator):
    """Request conforms to contract"""
    request = { ... }
    valid, error = validator.validate_request("<action>", request)
    assert valid

def test_<action>_response_schema(validator):
    """Response conforms to contract"""
    response = { ... }
    valid, error = validator.validate_response("<action>", response)
    assert valid

def test_<action>_backend_integration(ipc_service):
    """Backend handler returns valid response"""
    request = { ... }
    response = ipc_service._handle_<action>(request)
    valid, error = validator.validate_response("<action>", response)
    assert valid
```

### 2. Extension Manual Testing

After each feature:
```bash
# 1. Update contract
vim server/src/contracts/ipc_contract_v1.json

# 2. Run contract tests
pytest server/test/contract/ -v

# 3. Implement backend handler
vim server/src/services/ipc_service.py

# 4. Test backend
pytest server/test/services/test_ipc_service.py -k "<feature>"

# 5. Update extension
vim gnome-extension/src/adapters/GnomeSidePanel.js
vim gnome-extension/src/adapters/IPCClient.js

# 6. Install and test
./pack_install_run.sh

# 7. Trigger side panel and test feature
```

### 3. CI Integration

Update `.github/workflows/contract-tests.yml`:
```yaml
- name: Run all contract tests
  run: |
    pytest server/test/contract/ -v --cov=server/src/contracts

- name: Verify contract version bump
  run: |
    python scripts/check_contract_version.py
```

---

## Implementation Order

### Priority 1 (Essential for MVP)
1. **Search** - Most requested feature
2. **Filtering by type** - Quick access to specific content
3. **Delete items** - Privacy/cleanup

### Priority 2 (High Value)
4. **Favorites** - Quick bookmarking
5. **Pagination** - Performance for large history
6. **Image thumbnails** - Visual feedback

### Priority 3 (Nice to Have)
7. **Tags** - Advanced organization
8. **Sorting** - Different view modes
9. **Secrets** - Sensitive data protection
10. **Multi-select** - Batch operations

---

## Success Criteria

Each feature is complete when:
- [ ] Contract schema updated with new message types
- [ ] Contract tests pass (pytest)
- [ ] Backend IPC handler implemented
- [ ] Backend integration tests pass
- [ ] Extension UI implemented
- [ ] Manual testing confirms feature works
- [ ] No console errors in GNOME Shell logs
- [ ] Feature documented in PROGRESS.md

---

## Development Workflow

```bash
# 1. Start with contract
vim server/src/contracts/ipc_contract_v1.json

# 2. Write contract tests (TDD)
vim server/test/contract/test_<feature>.py
pytest server/test/contract/test_<feature>.py  # Should fail

# 3. Implement backend handler
vim server/src/services/ipc_service.py
pytest server/test/contract/test_<feature>.py  # Should pass

# 4. Implement extension UI
vim gnome-extension/src/adapters/GnomeSidePanel.js
vim gnome-extension/src/adapters/IPCClient.js

# 5. Test end-to-end
./pack_install_run.sh
# Trigger panel, test feature

# 6. Update progress
vim docs/PROGRESS.md
```

---

## Next Steps

**Ready to start?** Pick Priority 1 features and begin with:

1. Search contract definition
2. Search backend tests
3. Search backend implementation
4. Search extension UI
5. Integration testing

Let me know which feature to start with!
