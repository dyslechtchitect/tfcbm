# TFCBM UI Refactoring Plan v2.0

**Philosophy:** TDD, DI, PEP8, SOLID principles
**Goal:** Maintain 100% functionality while achieving clean, maintainable, testable code
**Approach:** Incremental refactoring with testing at each step

---

## Current State Analysis

### Problem Files
| File | Lines | Methods | Status |
|------|-------|---------|--------|
| clipboard_window.py | 2,940 | 70 | 🔴 Critical |
| clipboard_item_row.py | 1,741 | 34 | 🔴 Critical |
| main_window_builder.py | 571 | - | 🟡 Moderate |
| clipboard_list_manager.py | 377 | - | 🟢 Acceptable |

### SOLID Violations Identified

#### clipboard_window.py
**Single Responsibility Principle (SRP)** - Has 10+ responsibilities:
- Window lifecycle management
- History loading & pagination
- UI construction (tabs, filters, settings)
- WebSocket message handling
- Tag filtering
- Search coordination
- Sort coordination
- Notification display
- Settings management
- Keyboard shortcut handling

**Dependency Inversion Principle (DIP)**:
- Direct instantiation of services
- Tight coupling to GTK widgets

#### clipboard_item_row.py
**Single Responsibility Principle (SRP)** - Has 7+ responsibilities:
- UI rendering
- Clipboard operations
- File operations
- Secret management
- Drag & drop
- WebSocket communication
- Tag management

**Open/Closed Principle (OCP)**:
- Adding new clipboard types requires modifying the class

---

## Refactoring Strategy

### Phase 1: Extract Window Managers (Week 1)
**Goal:** Break down clipboard_window.py from 2,940 lines to <500 lines

#### 1.1 Extract TabManager (Day 1)
**File:** `ui/managers/tab_manager.py`

**Responsibilities:**
- Tab switching logic
- Tab-specific reloading
- Filter bar visibility per tab

**Methods to extract from clipboard_window.py:**
- `_on_tab_switched()`
- Tab switching state management

**Tests:** `tests/ui/managers/test_tab_manager.py`
- Test tab switching updates state
- Test filter bar visibility rules
- Test reload triggers

**Lines reduced:** ~100 lines

#### 1.2 Extract NotificationManager (Day 1)
**File:** `ui/managers/notification_manager.py`

**Responsibilities:**
- Show/hide notifications
- Notification timing
- Marquee animation handling

**Methods to extract:**
- `show_notification()`
- `_hide_notification()`

**Tests:** `tests/ui/managers/test_notification_manager.py`
- Test show notification
- Test auto-hide timer
- Test marquee for long messages

**Lines reduced:** ~50 lines

#### 1.3 Extract KeyboardShortcutHandler (Day 2)
**File:** `ui/handlers/keyboard_shortcut_handler.py`

**Responsibilities:**
- Handle keyboard events
- Copy on Return/Space
- Auto-focus search
- Auto-paste on keyboard activation

**Methods to extract:**
- `_on_key_pressed()`
- `_focus_first_item()`
- `_simulate_paste()` (currently in clipboard_item_row too!)

**Tests:** `tests/ui/handlers/test_keyboard_shortcut_handler.py`
- Test Return key copies item
- Test alphanumeric focuses search
- Test paste simulation

**Lines reduced:** ~150 lines

#### 1.4 Extract WindowPositionManager (Day 2)
**File:** `ui/managers/window_position_manager.py`

**Responsibilities:**
- Window positioning
- Monitor detection
- Size calculation

**Methods to extract:**
- `position_window_left()`
- Window sizing logic from `__init__`

**Tests:** `tests/ui/managers/test_window_position_manager.py`
- Test left positioning
- Test size calculation

**Lines reduced:** ~80 lines

#### 1.5 Move Settings to SettingsPage (Day 3)
**File:** `ui/pages/settings_page.py` (enhance existing)

**Currently:** 152 lines
**After:** ~300 lines (absorb all settings UI from clipboard_window.py)

**Methods to move:**
- `_create_settings_page()`
- `_on_save_settings()`
- All settings UI construction

**Tests:** `tests/ui/pages/test_settings_page.py`
- Test settings rendering
- Test save functionality
- Test validation

**Lines reduced from clipboard_window:** ~400 lines

#### 1.6 Extract FilterBarManager (Day 4)
**File:** `ui/managers/filter_bar_manager.py`

**Responsibilities:**
- Filter chip creation
- Filter toggle handling
- File extension filters
- Active filter tracking

**Methods to extract:**
- `_create_filter_bar()`
- `_create_filter_chip()`
- `_add_system_filters()`
- `_load_file_extensions()`
- `_on_filter_toggled()`
- `_on_clear_filters()`

**Tests:** `tests/ui/managers/test_filter_bar_manager.py`
- Test filter creation
- Test filter toggling
- Test clear filters
- Test system filters

**Lines reduced:** ~300 lines

#### 1.7 Extract TagFilterManager (Day 5)
**File:** `ui/managers/tag_filter_manager.py`

**Responsibilities:**
- Tag display in filter area
- Tag selection
- Tag-based filtering
- Drag & drop tags

**Methods to extract:**
- `_update_tags()`
- `_refresh_tag_display()`
- `_on_tag_clicked()`
- `_apply_tag_filter()`
- `_clear_tag_filter()`
- `_restore_filtered_view()`
- `_on_tag_drag_prepare()`
- `_on_tag_drag_begin()`

**Tests:** `tests/ui/managers/test_tag_filter_manager.py`
- Test tag display
- Test tag filtering
- Test drag and drop

**Lines reduced:** ~250 lines

#### 1.8 Extract UserTagsManager (Day 5)
**File:** `ui/managers/user_tags_manager.py`

**Responsibilities:**
- User tags CRUD UI
- Tag dialogs (create/edit/delete)
- User tags display refresh

**Methods to extract:**
- `_refresh_user_tags_display()`
- `_on_create_tag()`
- `_on_edit_tag()`
- `_on_delete_tag()`
- `_on_tag_dropped_on_item()`

**Tests:** `tests/ui/managers/test_user_tags_manager.py`
- Test create tag dialog
- Test edit tag
- Test delete confirmation
- Test tag drop on item

**Lines reduced:** ~350 lines

**Phase 1 Result:**
clipboard_window.py: 2,940 → ~1,260 lines (57% reduction)

---

### Phase 2: Extract Item Row Operations (Week 2)
**Goal:** Break down clipboard_item_row.py from 1,741 lines to <400 lines

#### 2.1 Extract ClipboardOperationsHandler (Day 6-7)
**File:** `ui/handlers/clipboard_operations_handler.py`

**Responsibilities:**
- Copy to clipboard
- Record paste events
- Handle different content types (text, image, file, folder)

**Methods to extract:**
- `_perform_copy_to_clipboard()`
- `_copy_full_image_to_clipboard()`
- `_copy_file_to_clipboard()`
- `_copy_folder_to_clipboard()`
- `_copy_regular_file_to_clipboard()`
- `_record_paste()`

**Tests:** `tests/ui/handlers/test_clipboard_operations_handler.py`
- Test copy text
- Test copy image
- Test copy file
- Test copy folder
- Test paste recording

**Lines reduced:** ~450 lines

#### 2.2 Extract FileOperationsHandler (Day 8)
**File:** `ui/handlers/file_operations_handler.py`

**Responsibilities:**
- Save file dialogs
- View file dialogs
- File download/save operations

**Methods to extract:**
- `_show_save_dialog()`
- `_show_view_dialog()`
- File metadata parsing

**Tests:** `tests/ui/handlers/test_file_operations_handler.py`
- Test save dialog
- Test view dialog
- Test file operations

**Lines reduced:** ~200 lines

#### 2.3 Extract SecretOperationsHandler (Day 9)
**File:** `ui/handlers/secret_operations_handler.py`

**Responsibilities:**
- Secret authentication
- Secret content fetching
- Secret status toggling
- Secret naming

**Methods to extract:**
- `_fetch_secret_content()`
- `_toggle_secret_status()`
- `_show_auth_required_notification()`
- `_show_fetch_error_notification()`
- Secret state management

**Tests:** `tests/ui/handlers/test_secret_operations_handler.py`
- Test authentication required
- Test content fetching
- Test toggle secret status
- Test secret naming

**Lines reduced:** ~300 lines

#### 2.4 Extract DragDropHandler (Day 10)
**File:** `ui/handlers/drag_drop_handler.py`

**Responsibilities:**
- Drag source setup
- Drag data preparation
- Drop target handling
- File prefetching for DnD

**Methods to extract:**
- `_on_drag_prepare()`
- `_on_drag_begin()`
- `_prefetch_file_for_dnd()`
- Drop target handling

**Tests:** `tests/ui/handlers/test_drag_drop_handler.py`
- Test drag preparation
- Test file prefetch
- Test drop handling

**Lines reduced:** ~200 lines

#### 2.5 Extract ItemActionsCoordinator (Day 11)
**File:** `ui/coordinators/item_actions_coordinator.py`

**Responsibilities:**
- Coordinate all item actions (copy, view, save, delete, tags, secret)
- Delegate to appropriate handlers
- Action button callbacks

**Methods to extract:**
- `_on_copy_action()`
- `_on_view_action()`
- `_on_save_action()`
- `_on_tags_action()`
- `_on_secret_action()`
- `_on_delete_action()`

**Tests:** `tests/ui/coordinators/test_item_actions_coordinator.py`
- Test action routing
- Test handler delegation

**Lines reduced:** ~150 lines

#### 2.6 Refactor ClipboardItemRow to Composition (Day 12)
**File:** `ui/rows/clipboard_item_row.py` (refactored)

**New structure:**
```python
class ClipboardItemRow(Gtk.ListBoxRow):
    """Lightweight row that composes handlers."""

    def __init__(self, item, window, ...):
        # UI setup only
        self.clipboard_ops = ClipboardOperationsHandler(...)
        self.file_ops = FileOperationsHandler(...)
        self.secret_ops = SecretOperationsHandler(...)
        self.drag_drop = DragDropHandler(...)
        self.actions_coordinator = ItemActionsCoordinator(
            clipboard_ops=self.clipboard_ops,
            file_ops=self.file_ops,
            secret_ops=self.secret_ops,
            ...
        )
```

**Responsibilities (reduced):**
- UI construction only
- Delegate all actions to handlers/coordinators
- Tag display (uses ItemTags component)

**Tests:** `tests/ui/rows/test_clipboard_item_row.py`
- Test UI construction
- Test handler wiring
- Test action delegation

**Phase 2 Result:**
clipboard_item_row.py: 1,741 → ~350 lines (80% reduction)

---

### Phase 3: Enhance Builder Pattern (Week 3)

#### 3.1 Split MainWindowBuilder (Day 13-14)
**Current:** 571 lines

**Split into:**
1. `ui/builders/tab_view_builder.py` (~150 lines)
   - Build tab view with copied/pasted/tags tabs
2. `ui/builders/filter_bar_builder.py` (~120 lines)
   - Build filter bar with chips (move from FilterBarManager)
3. `ui/builders/toolbar_builder.py` (~80 lines)
   - Build toolbar with search, sort, jump buttons
4. `ui/builders/main_window_builder.py` (~200 lines)
   - Orchestrate all sub-builders
   - Build main window structure

**Tests:**
- `tests/ui/builders/test_tab_view_builder.py`
- `tests/ui/builders/test_filter_bar_builder.py`
- `tests/ui/builders/test_toolbar_builder.py`
- `tests/ui/builders/test_main_window_builder.py`

#### 3.2 Extract DialogFactory (Day 15)
**File:** `ui/factories/dialog_factory.py`

**Responsibilities:**
- Create standard dialogs (save, view, confirm)
- Create tag dialogs
- Create secret naming dialogs

**Tests:** `tests/ui/factories/test_dialog_factory.py`

---

### Phase 4: Protocol-Based Architecture (Week 4)

#### 4.1 Define Core Protocols (Day 16-17)
**File:** `ui/core/protocols.py` (enhance existing)

Add protocols for:
```python
class ClipboardOperations(Protocol):
    def copy_to_clipboard(self, item: Dict) -> None: ...
    def record_paste(self, item_id: int) -> None: ...

class FileOperations(Protocol):
    def save_file(self, item: Dict) -> None: ...
    def view_file(self, item: Dict) -> None: ...

class SecretOperations(Protocol):
    def fetch_secret(self, item_id: int) -> Optional[str]: ...
    def toggle_secret_status(self, item_id: int, is_secret: bool) -> None: ...

class NotificationService(Protocol):
    def show(self, message: str) -> None: ...
    def hide(self) -> None: ...

class TabManagement(Protocol):
    def switch_tab(self, tab_name: str) -> None: ...
    def reload_current_tab(self) -> None: ...
```

#### 4.2 Update All Handlers to Use Protocols (Day 18-19)
- Update handler constructors to accept Protocol types
- Enable easy mocking in tests
- Improve testability

---

### Phase 5: Testing Infrastructure (Week 5)

#### 5.1 Create Test Fixtures (Day 20)
**File:** `tests/fixtures.py`

Create reusable fixtures:
- Mock clipboard items (text, image, file, secret)
- Mock GTK widgets
- Mock services
- Mock window states

#### 5.2 Write Integration Tests (Day 21-22)
**Files:** `tests/integration/`

Test workflows:
- Copy text item → paste → verify in recently pasted
- Mark item as secret → authenticate → view → verify
- Filter by tag → verify filtered items
- Search → verify results
- Sort → verify order

#### 5.3 Write Unit Tests for All Managers (Day 23-24)
- Achieve >80% coverage for managers
- Test all edge cases
- Test error handling

---

## Execution Strategy

### Incremental Approach
1. **Never break main** - All changes must maintain functionality
2. **Test after each extraction** - Run app after every file extraction
3. **Commit frequently** - Small, atomic commits
4. **Branch per phase** - `refactor/phase-1-window-managers`, etc.

### Testing Checklist (Run After Each Change)
- [ ] App launches successfully
- [ ] Copy item works
- [ ] View item works
- [ ] Save item works
- [ ] Delete item works
- [ ] Secrets work (mark, authenticate, view)
- [ ] Tags work (create, assign, filter)
- [ ] Search works
- [ ] Sort works
- [ ] Filter works
- [ ] Tab switching works
- [ ] Keyboard shortcuts work (Ctrl+`, Return/Space to copy)
- [ ] Recently pasted shows items
- [ ] Settings save works

### Code Quality Standards
- **PEP8 compliance** - Use black, flake8, mypy
- **Type hints** - All public methods
- **Docstrings** - Google style for all classes and public methods
- **Line limit** - Max 500 lines per file
- **Method limit** - Max 20 methods per class
- **Complexity** - Max cyclomatic complexity of 10

---

## Expected Outcomes

### Metrics
| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Largest file | 2,940 lines | ~500 lines | 83% reduction |
| Avg file size | ~350 lines | ~150 lines | 57% reduction |
| clipboard_window methods | 70 | <15 | 79% reduction |
| clipboard_item_row methods | 34 | <10 | 71% reduction |
| Test coverage | ~0% | >80% | New capability |
| Testable units | 5 | 30+ | 6x increase |

### Benefits
1. **Maintainability** - Easy to find and fix bugs
2. **Testability** - Each component can be unit tested
3. **Extensibility** - Add new features without modifying existing code
4. **Readability** - Clear separation of concerns
5. **Reusability** - Components can be reused
6. **Debuggability** - Smaller units are easier to debug
7. **Onboarding** - New developers can understand code faster

---

## Risk Mitigation

### Risks
1. **Breaking functionality** during extraction
2. **Regression bugs** from refactoring
3. **Integration issues** between new components
4. **Performance degradation** from increased abstraction

### Mitigation Strategies
1. **Incremental changes** - Extract one piece at a time
2. **Comprehensive testing** - Test after each change
3. **Rollback plan** - Keep stash points at each phase
4. **Performance monitoring** - Monitor app launch time and responsiveness
5. **Code review** - Review each phase before proceeding
6. **User feedback loop** - Test real-world usage after each phase

---

## Timeline

### 5-Week Plan
- **Week 1:** Phase 1 - Extract window managers (clipboard_window.py cleanup)
- **Week 2:** Phase 2 - Extract item row operations (clipboard_item_row.py cleanup)
- **Week 3:** Phase 3 - Enhance builder pattern
- **Week 4:** Phase 4 - Protocol-based architecture
- **Week 5:** Phase 5 - Testing infrastructure

### Daily Commitment
- 2-3 hours per day
- Extract → Test → Commit cycle
- End each day with working app

---

## Success Criteria

### Must Have
- [x] 100% functionality preserved
- [x] No user-visible changes (unless bugs fixed)
- [x] All existing features work
- [x] App launches successfully

### Should Have
- [x] >80% test coverage for managers
- [x] All files <500 lines
- [x] All classes <20 methods
- [x] PEP8 compliant

### Nice to Have
- [x] Performance improvements
- [x] Reduced memory footprint
- [x] Faster startup time

---

## Post-Refactoring

### Documentation
1. Update architecture docs
2. Create component diagrams
3. Write contribution guide
4. Document testing strategy

### Future Work
1. Server-side refactoring (separate plan)
2. Add more integration tests
3. Performance profiling and optimization
4. Accessibility improvements

---

## Notes

This is a **living document** - update as we learn and adapt during refactoring.

**Remember:** The goal is not perfection, but significant improvement with zero functionality loss.

---

**Created:** 2025-12-03
**Version:** 2.0
**Status:** Ready for execution
