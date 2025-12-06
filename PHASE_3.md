# Phase 3: Builder Pattern & Component Extraction

**Objective**: Eliminate anti-patterns across the entire UI project, focusing on readability, testability, and maintainability while preserving all functionality and optimizing performance.

**Principles**: SOLID, DRY, Clean Code, TDD

---

## Anti-Patterns Identified

### 1. **CRITICAL: Unused Builder Pattern** ❌
- `ui/builders/main_window_builder.py` exists (571 lines) but is **NOT USED**
- `clipboard_window.py` still constructs all UI inline (~400 lines in `__init__`)
- **Impact**: Violates SRP, poor testability, difficult to maintain

### 2. **CRITICAL: God Object - ClipboardItemRow** ❌
- **1,741 lines** in a single class (largest file in UI)
- Handles: UI construction, clipboard operations, WebSocket calls, drag-drop, secrets, tags, deletion
- **Impact**: Violates SRP massively, impossible to test, tightly coupled

### 3. Large Manager Files
- `history_loader_manager.py`: 579 lines (acceptable - complex business logic)
- `clipboard_list_manager.py`: 377 lines (review needed)
- `user_tags_manager.py`: 373 lines (review needed)
- `filter_bar_manager.py`: 353 lines (review needed)

---

## Phase 3 Implementation Plan

### **Task 3.1: Use Existing MainWindowBuilder**
**Priority**: HIGH
**Est. Line Reduction**: ~350 lines from clipboard_window.py
**Status**: Ready to implement

**Actions**:
1. ✅ Review `ui/builders/main_window_builder.py` implementation
2. Integrate MainWindowBuilder into `clipboard_window.py.__init__`
3. Remove inline UI construction from clipboard_window.py
4. Update manager initialization to use builder-provided widgets
5. Test all UI functionality

**Before**:
```python
# clipboard_window.py __init__ (~500 lines)
def __init__(self, app, server_pid=None):
    # ... 400 lines of UI construction ...
    self.header = Adw.HeaderBar()
    self.search_entry = Gtk.SearchEntry()
    # ... etc ...
```

**After**:
```python
# clipboard_window.py __init__ (~150 lines)
def __init__(self, app, server_pid=None):
    # ... basic setup ...
    builder = MainWindowBuilder(self)
    widgets = builder.build()

    # Store widget references
    self.header = widgets.header
    self.search_entry = widgets.search_entry
    # ... initialize managers with widgets ...
```

---

### **Task 3.2: Refactor ClipboardItemRow (God Object → Components)**
**Priority**: CRITICAL
**Est. Line Reduction**: Split 1,741 lines into ~8 focused classes
**Status**: Planning

**Current Structure** (1,741 lines):
- UI construction: ~200 lines
- Clipboard operations: ~300 lines
- WebSocket operations: ~400 lines
- Drag & drop: ~150 lines
- Secret management: ~250 lines
- Tag management: ~200 lines
- Delete operations: ~100 lines
- Event handlers: ~140 lines

**Target Architecture**:

```
ClipboardItemRow (150 lines) - Coordinator only
├── ClipboardItemRowBuilder (200 lines) - UI construction
├── ClipboardOperationsHandler (300 lines) - Copy/paste/pin
├── ItemWebSocketService (400 lines) - Server communication
├── ItemDragDropHandler (150 lines) - Drag & drop
├── ItemSecretManager (250 lines) - Secret operations
├── ItemTagManager (200 lines) - Tag operations
└── ItemDeleteHandler (100 lines) - Delete operations
```

**Implementation Steps**:
1. Create `ui/rows/handlers/` directory
2. Extract `ClipboardOperationsHandler`
3. Extract `ItemWebSocketService`
4. Extract `ItemDragDropHandler`
5. Extract `ItemSecretManager`
6. Extract `ItemTagManager`
7. Extract `ItemDeleteHandler`
8. Create `ui/rows/builders/clipboard_item_row_builder.py`
9. Refactor `ClipboardItemRow` to coordinator pattern
10. Test all functionality

---

### **Task 3.3: Extract Composite Components**
**Priority**: MEDIUM
**Est. Line Reduction**: ~100 lines per component

**Components to Create**:

1. **SearchBarComponent** (`ui/components/search_bar.py` - already exists, verify)
   - Self-contained Gtk.Box
   - Handles own layout and signals
   - ~50 lines

2. **TagFilterComponent** (`ui/components/tag_filter.py`)
   - Tag flowbox with clear button
   - Self-managing state
   - ~80 lines

3. **StatusFooterComponent** (`ui/components/status_footer.py`)
   - Status label and loader
   - Reusable across tabs
   - ~40 lines

4. **TabContentComponent** (`ui/components/tab_content.py`)
   - Scrolled window + listbox + footer
   - Eliminates duplicate code
   - ~100 lines

---

### **Task 3.4: Review and Optimize Large Managers**
**Priority**: LOW
**Est. Impact**: Improve readability, identify extraction opportunities

**Files to Review**:
1. `clipboard_list_manager.py` (377 lines)
2. `user_tags_manager.py` (373 lines)
3. `filter_bar_manager.py` (353 lines)

**Review Criteria**:
- Single Responsibility Principle adherence
- Method length (should be <50 lines)
- Cyclomatic complexity
- Testability
- Potential for further extraction

---

### **Task 3.5: Introduce Dependency Injection Container**
**Priority**: LOW (Future Enhancement)
**Status**: Deferred

Check if `ui/core/di_container.py` is implemented:
- If yes, integrate with managers
- If no, defer until testing infrastructure is needed

---

## Success Metrics

### Line Count Targets
- [x] **Phase 1-2**: clipboard_window.py: 2027 → 999 lines ✅
- [ ] **Phase 3.1**: clipboard_window.py: 999 → ~600 lines (use builder)
- [ ] **Phase 3.2**: clipboard_item_row.py: 1741 → ~150 lines (extract handlers)
- [ ] **Overall**: Reduce total UI codebase by ~1,000 additional lines

### Quality Metrics
- [ ] All classes follow SRP
- [ ] All methods <50 lines
- [ ] All classes <300 lines (except complex business logic)
- [ ] Zero God Objects
- [ ] All UI construction in builders or components
- [ ] 100% functionality preserved
- [ ] No performance regression

### Testability Metrics
- [ ] All business logic classes are unit-testable
- [ ] UI components can be instantiated in isolation
- [ ] Dependencies are injected, not created

---

## Implementation Order

**Week 1**:
1. ✅ Create PHASE_3.md plan
2. Task 3.1: Integrate MainWindowBuilder (HIGH priority)

**Week 2**:
3. Task 3.2: Refactor ClipboardItemRow (CRITICAL priority)
   - Days 1-2: Extract handlers
   - Days 3-4: Create builder
   - Day 5: Refactor coordinator

**Week 3**:
4. Task 3.3: Extract composite components
5. Task 3.4: Review large managers

---

## Testing Strategy

**For Each Refactoring**:
1. Run application before changes (baseline)
2. Make incremental changes
3. Test after each major extraction:
   - Application starts
   - All UI renders correctly
   - All interactions work (click, paste, drag, etc.)
   - WebSocket communication works
   - No console errors
4. Performance check: startup time should not increase

**Manual Test Checklist**:
- [ ] Application starts without errors
- [ ] Search functionality works
- [ ] Filter functionality works
- [ ] Sort functionality works
- [ ] Tab switching works
- [ ] Copy to clipboard works
- [ ] Paste works
- [ ] Item deletion works
- [ ] Tag management works
- [ ] Secret management works
- [ ] Drag & drop works
- [ ] Settings page works
- [ ] No memory leaks (visual check)

---

## Rollback Strategy

- Commit after each completed task
- Use feature branches for large refactorings
- Keep git history clean with descriptive commits
- Each commit should be independently testable

---

## Notes

- **DO NOT** optimize prematurely - measure before optimizing
- **DO** preserve all existing functionality
- **DO** test thoroughly after each change
- **DO** commit frequently with clear messages
- **AVOID** big-bang refactorings - incremental is safer

---

**Started**: 2025-12-06
**Target Completion**: 2025-12-27
**Current Status**: Task 3.1 in progress
