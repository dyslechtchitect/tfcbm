# Phase 2: Additional Refactoring Plan

## Current Status
- clipboard_window.py: **2027 lines** ❌ TOO LARGE
- Phase 1 complete: 8 managers extracted
- Phase 2 in progress

## Remaining Extractions (Priority Order)

### Phase 2.2: SearchManager (~150 lines to extract)
**Location**: `ui/managers/search_manager.py`
**Responsibility**: Search functionality with debouncing
**Methods to extract from clipboard_window.py**:
- `_on_search_changed()` 
- `_on_search_activate()`
- `_perform_search()`
- `_display_search_results()`
- `_restore_normal_view()`
**State to move**:
- `search_query`, `search_timer`, `search_active`, `search_results`

### Phase 2.3: SortManager (~120 lines)
**Location**: `ui/managers/sort_manager.py`
**Responsibility**: Sort state and operations
**Methods**:
- `_toggle_sort()`
- `_reload_copied_with_sort()`
- `_reload_pasted_with_sort()`
**State**:
- `copied_sort_order`, `pasted_sort_order`

### Phase 2.4: TagDialogManager (~200+ lines)
**Location**: `ui/managers/tag_dialog_manager.py`
**Responsibility**: Tag creation/editing dialogs
**Methods**:
- `_on_create_tag()`
- `_on_edit_tag()`
- `_update_tag_on_server()`
**Note**: Color picker UI logic should be extracted

### Phase 2.5: TagDisplayManager (~100 lines)
**Location**: `ui/managers/tag_display_manager.py`
**Responsibility**: Tag display in filter area (bottom of window)
**Methods**:
- `load_tags()`
- `_update_tags()`
- `_refresh_tag_display()`
**State**:
- `all_tags`, `tag_buttons`

### Phase 2.6: PaginationManager (~150 lines)
**Location**: Extract into existing `ui/managers/pagination_manager.py` or create new
**Responsibility**: Infinite scroll and pagination
**Methods**:
- `_on_scroll_changed()`
- `_load_more_copied_items()`
- `_load_more_pasted_items()`
- `_fetch_more_items()`
- `_append_items_to_listbox()`

### Phase 2.7: ItemListManager (~100 lines)
**Location**: `ui/managers/item_list_manager.py`
**Responsibility**: Listbox operations
**Methods**:
- `update_history()`
- `update_pasted_history()`
- `add_item()`
- `remove_item()`
- `_update_copied_status()`

## Expected Result
After Phase 2 completion:
- **Target**: clipboard_window.py < 1000 lines
- **Reduction**: ~1000+ lines extracted
- Better separation of concerns
- Easier testing and maintenance

## Implementation Pattern
For each extraction:
1. Create manager class with clear responsibility
2. Initialize in clipboard_window.__init__()
3. Replace method calls with manager delegation
4. Remove old methods
5. Update __init__.py exports
6. Syntax verification
7. Test functionality

## Key Principles
- **Single Responsibility**: Each manager handles ONE concern
- **Dependency Injection**: Pass dependencies via constructor
- **Callback Pattern**: Use callbacks for communication
- **Clean separation**: UI vs Logic vs Data
