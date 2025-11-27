# TFCBM UI Refactoring Plan

## Executive Summary

Transform the monolithic 4,423-line `ui/main.py` into a modern, testable, SOLID-compliant architecture with full dependency injection. This plan focuses on the UI component as phase 1 of the project-wide refactoring.

## Current State Analysis

### Problems
- **Monolithic**: Single 4,423-line file with 146 methods
- **God Object**: `ClipboardWindow` handles everything (UI, business logic, data access)
- **Hard Dependencies**: Direct database calls, file system access, clipboard operations
- **Untestable**: No dependency injection, tight coupling, global state
- **Mixed Concerns**: UI rendering mixed with business logic and data access
- **No Interfaces**: Concrete implementations everywhere
- **Poor Separation**: One class handles 10+ responsibilities

### Current Structure
```
ui/main.py (4,423 lines)
├── highlight_text()                    # Utility function
├── ClipboardItemRow (63-1864)          # 1,800 lines!
│   ├── Rendering
│   ├── Tag management
│   ├── Clipboard operations
│   ├── File operations
│   └── Drag & Drop
└── ClipboardWindow (1865-4218)         # 2,353 lines!
    ├── Window management
    ├── Tab management
    ├── Filter management
    ├── Search functionality
    ├── Settings management
    ├── Tag management
    ├── Pagination
    ├── Database access
    └── Clipboard operations
```

---

## Target Architecture

### Design Principles
1. **SOLID Principles**: Single responsibility, Open/closed, Liskov substitution, Interface segregation, Dependency inversion
2. **Dependency Injection**: All dependencies injected via constructors
3. **Protocol-Based**: Use Python protocols for interfaces
4. **Pure Functions**: Extract utilities as pure functions
5. **Immutable Configuration**: Settings as immutable dataclasses
6. **PEP 8 Compliance**: 79 char lines, proper naming, type hints
7. **Testability First**: Every component independently testable

### File Size Limits
- **Maximum file size**: 300 lines
- **Maximum class size**: 150 lines
- **Maximum method size**: 30 lines
- **Maximum function size**: 20 lines

---

## New Directory Structure

```
ui/
├── __init__.py
├── main.py                          # Entry point only (~50 lines)
│
├── config/                          # Configuration management
│   ├── __init__.py
│   ├── settings.py                  # Settings dataclass
│   ├── paths.py                     # Path configuration
│   └── loader.py                    # Config file loader
│
├── core/                            # Core protocols and interfaces
│   ├── __init__.py
│   ├── protocols.py                 # Protocol definitions
│   ├── events.py                    # Event system
│   └── di_container.py              # Dependency injection container
│
├── models/                          # Data models (already exists)
│   ├── __init__.py
│   ├── clipboard_item.py            # ✓ Created
│   └── tag.py                       # ✓ Created
│
├── services/                        # Business logic (already exists)
│   ├── __init__.py
│   ├── clipboard_service.py         # ✓ Created - System clipboard
│   ├── database_service.py          # ✓ Created - Database operations
│   ├── search_service.py            # ✓ Created - Search & filtering
│   ├── tag_service.py               # ✓ Created - Tag operations
│   ├── file_service.py              # NEW - File operations
│   ├── websocket_service.py         # NEW - Server communication
│   └── pagination_service.py        # NEW - Pagination logic
│
├── utils/                           # Pure utility functions (exists)
│   ├── __init__.py
│   ├── formatting.py                # ✓ Created - Text formatting
│   ├── highlighting.py              # ✓ Created - Search highlighting
│   └── gtk_utils.py                 # NEW - GTK helper functions
│
├── components/                      # UI Components
│   ├── __init__.py
│   │
│   ├── base/                        # Base component classes
│   │   ├── __init__.py
│   │   ├── component.py             # Base component protocol
│   │   └── list_item.py             # Base list item component
│   │
│   ├── items/                       # Item-related components
│   │   ├── __init__.py
│   │   ├── clipboard_item_row.py    # Clipboard item display
│   │   ├── item_header.py           # Item header (timestamp, name)
│   │   ├── item_content.py          # Content display (text/image/file)
│   │   ├── item_actions.py          # Action buttons
│   │   └── item_tags.py             # Tag display and management
│   │
│   ├── dialogs/                     # Dialog components
│   │   ├── __init__.py
│   │   ├── full_item_dialog.py      # Full item view dialog
│   │   ├── tag_editor_dialog.py     # Tag editor
│   │   └── settings_dialog.py       # Settings (if needed)
│   │
│   ├── panels/                      # Panel components
│   │   ├── __init__.py
│   │   ├── header_bar.py            # Application header
│   │   ├── filter_bar.py            # Filter toolbar
│   │   ├── search_bar.py            # Search input
│   │   ├── tag_panel.py             # Tag management panel
│   │   └── settings_panel.py        # Settings panel
│   │
│   ├── lists/                       # List components
│   │   ├── __init__.py
│   │   ├── clipboard_list.py        # Clipboard item list
│   │   ├── paged_list.py            # List with pagination
│   │   └── infinite_scroll_list.py  # Infinite scroll handler
│   │
│   └── widgets/                     # Small reusable widgets
│       ├── __init__.py
│       ├── filter_chip.py           # Filter button chip
│       ├── tag_chip.py              # Tag display chip
│       ├── loader_spinner.py        # Loading indicator
│       └── status_label.py          # Status message display
│
├── windows/                         # Top-level windows
│   ├── __init__.py
│   ├── main_window.py               # Main application window
│   ├── about_window.py              # About dialog (exists)
│   └── splash_window.py             # Splash screen (if separate)
│
└── application.py                   # Application class
```

---

## Phase 1: Foundation (Week 1)

### 1.1 Configuration System
**Goal**: Make all settings and paths injectable

**Files to Create**:
- `ui/config/settings.py`
- `ui/config/paths.py`
- `ui/config/loader.py`

**Implementation**:
```python
# config/settings.py
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class DisplaySettings:
    """Display configuration."""
    item_width: int = 300
    item_height: int = 150
    max_page_length: int = 50

@dataclass(frozen=True)
class WindowSettings:
    """Window configuration."""
    default_width: int = 350
    default_height: int = 800
    position: str = "left"  # left, right, center

@dataclass(frozen=True)
class AppSettings:
    """Application settings."""
    display: DisplaySettings
    window: WindowSettings

    @classmethod
    def load(cls, path: Optional[str] = None) -> "AppSettings":
        """Load settings from file or use defaults."""
        # Implementation
```

```python
# config/paths.py
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

@dataclass(frozen=True)
class AppPaths:
    """Application paths configuration."""
    db_path: Path
    config_path: Path
    css_path: Path
    resources_path: Path

    @classmethod
    def default(cls) -> "AppPaths":
        """Get default paths."""
        home = Path.home()
        return cls(
            db_path=home / ".local" / "share" / "tfcbm" / "clipboard.db",
            config_path=Path("settings.yml"),
            css_path=Path(__file__).parent.parent / "style.css",
            resources_path=Path(__file__).parent.parent.parent / "resouces",
        )
```

### 1.2 Core Protocols
**Goal**: Define interfaces for all dependencies

**File**: `ui/core/protocols.py`

```python
from typing import Protocol, List, Optional
from models import ClipboardItem, Tag

class DatabasePort(Protocol):
    """Database operations interface."""
    def get_history(
        self,
        limit: int,
        offset: int,
        sort_asc: bool = False,
        type_filter: Optional[str] = None,
    ) -> List[dict]: ...

    def search_items(self, query: str, limit: int) -> List[dict]: ...
    def update_item_name(self, item_id: int, name: str) -> None: ...
    def delete_item(self, item_id: int) -> None: ...

class ClipboardPort(Protocol):
    """Clipboard operations interface."""
    def copy_text(self, text: str) -> None: ...
    def copy_image(self, texture) -> None: ...
    def get_text(self) -> str: ...

class FileServicePort(Protocol):
    """File operations interface."""
    def save_file(self, data: bytes, path: str) -> None: ...
    def read_file(self, path: str) -> bytes: ...

class TagServicePort(Protocol):
    """Tag operations interface."""
    def get_all_tags(self) -> List[Tag]: ...
    def create_tag(self, name: str) -> int: ...
    def delete_tag(self, tag_id: int) -> None: ...
    def add_tag_to_item(self, item_id: int, tag_id: int) -> None: ...
```

### 1.3 Dependency Injection Container
**Goal**: Central place for dependency wiring

**File**: `ui/core/di_container.py`

```python
from dataclasses import dataclass
from config import AppSettings, AppPaths
from services import (
    DatabaseService,
    ClipboardService,
    TagService,
    FileService,
)

@dataclass
class AppContainer:
    """Dependency injection container."""
    settings: AppSettings
    paths: AppPaths

    # Services (lazy initialization)
    _db_service: Optional[DatabaseService] = None
    _clipboard_service: Optional[ClipboardService] = None
    _tag_service: Optional[TagService] = None
    _file_service: Optional[FileService] = None

    @property
    def db_service(self) -> DatabaseService:
        if self._db_service is None:
            self._db_service = DatabaseService(str(self.paths.db_path))
        return self._db_service

    @property
    def clipboard_service(self) -> ClipboardService:
        if self._clipboard_service is None:
            self._clipboard_service = ClipboardService()
        return self._clipboard_service

    @property
    def tag_service(self) -> TagService:
        if self._tag_service is None:
            self._tag_service = TagService(self.db_service.db)
        return self._tag_service

    @classmethod
    def create(
        cls,
        settings: Optional[AppSettings] = None,
        paths: Optional[AppPaths] = None,
    ) -> "AppContainer":
        """Create container with optional overrides."""
        return cls(
            settings=settings or AppSettings.load(),
            paths=paths or AppPaths.default(),
        )
```

---

## Phase 2: Service Layer Completion (Week 2)

### 2.1 New Services to Create

#### File Service
**File**: `ui/services/file_service.py`

```python
from pathlib import Path
from typing import Optional
from config import AppPaths

class FileService:
    """Handles file operations."""

    def __init__(self, paths: AppPaths):
        self.paths = paths

    def save_image(self, data: bytes, suggested_name: str) -> Optional[str]:
        """Save image with file dialog."""
        # Implementation

    def save_text(self, text: str, suggested_name: str) -> Optional[str]:
        """Save text file with dialog."""
        # Implementation
```

#### Pagination Service
**File**: `ui/services/pagination_service.py`

```python
from dataclasses import dataclass
from typing import Callable, Generic, TypeVar, List

T = TypeVar('T')

@dataclass
class PageState:
    """Pagination state."""
    offset: int = 0
    total: int = 0
    page_size: int = 50
    has_more: bool = True
    loading: bool = False

class PaginationService(Generic[T]):
    """Manages pagination logic."""

    def __init__(self, page_size: int):
        self.page_size = page_size
        self.state = PageState(page_size=page_size)

    def load_next_page(
        self,
        loader: Callable[[int, int], List[T]]
    ) -> List[T]:
        """Load next page of items."""
        if not self.state.has_more or self.state.loading:
            return []

        self.state.loading = True
        items = loader(self.state.page_size, self.state.offset)

        self.state.offset += len(items)
        self.state.has_more = len(items) == self.state.page_size
        self.state.loading = False

        return items

    def reset(self) -> None:
        """Reset pagination state."""
        self.state = PageState(page_size=self.page_size)
```

#### WebSocket Service
**File**: `ui/services/websocket_service.py`

```python
import asyncio
import json
from typing import Callable, Optional

class WebSocketService:
    """Handles WebSocket communication with server."""

    def __init__(self, uri: str = "ws://localhost:8765"):
        self.uri = uri
        self.websocket = None

    async def connect(self) -> None:
        """Connect to WebSocket server."""
        # Implementation

    async def get_full_image(self, item_id: int) -> Optional[bytes]:
        """Request full image from server."""
        # Implementation

    async def delete_item(self, item_id: int) -> bool:
        """Delete item via server."""
        # Implementation
```

---

## Phase 3: Component Extraction (Week 3-4)

### 3.1 Base Components

#### Base Component Protocol
**File**: `ui/components/base/component.py`

```python
from typing import Protocol
from gi.repository import Gtk

class Component(Protocol):
    """Base component protocol."""

    def build(self) -> Gtk.Widget:
        """Build and return the widget."""
        ...

    def destroy(self) -> None:
        """Clean up component resources."""
        ...
```

### 3.2 ClipboardItemRow Refactoring

**Current**: 1,800 lines in one class
**Target**: 6 focused classes

#### Main Row Component
**File**: `ui/components/items/clipboard_item_row.py` (~150 lines)

```python
from gi.repository import Gtk
from models import ClipboardItem
from components.items import (
    ItemHeader,
    ItemContent,
    ItemActions,
    ItemTags,
)
from services import ClipboardService, TagService
from config import DisplaySettings

class ClipboardItemRow(Gtk.ListBoxRow):
    """Main clipboard item row component."""

    def __init__(
        self,
        item: ClipboardItem,
        clipboard_service: ClipboardService,
        tag_service: TagService,
        settings: DisplaySettings,
        search_query: str = "",
    ):
        super().__init__()
        self.item = item
        self.clipboard_service = clipboard_service
        self.tag_service = tag_service
        self.settings = settings
        self.search_query = search_query

        self._build_ui()

    def _build_ui(self) -> None:
        """Build the row UI."""
        # Container
        card = Gtk.Frame()
        card.add_css_class("clipboard-item-card")
        card.set_size_request(self.settings.item_width, -1)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        # Components
        self.header = ItemHeader(
            self.item,
            search_query=self.search_query
        )
        box.append(self.header.build())

        self.content = ItemContent(
            self.item,
            self.settings,
            search_query=self.search_query
        )
        box.append(self.content.build())

        self.actions = ItemActions(
            self.item,
            clipboard_service=self.clipboard_service
        )
        box.append(self.actions.build())

        self.tags = ItemTags(
            self.item,
            tag_service=self.tag_service
        )
        box.append(self.tags.build())

        card.set_child(box)
        self.set_child(card)
```

#### Item Header Component
**File**: `ui/components/items/item_header.py` (~80 lines)

```python
from gi.repository import Gtk
from models import ClipboardItem
from utils import format_timestamp, highlight_text

class ItemHeader:
    """Item header with timestamp and name."""

    def __init__(self, item: ClipboardItem, search_query: str = ""):
        self.item = item
        self.search_query = search_query

    def build(self) -> Gtk.Widget:
        """Build header widget."""
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        # Timestamp
        timestamp_text = format_timestamp(self.item.timestamp)
        timestamp_label = Gtk.Label(label=f"Copied: {timestamp_text}")
        timestamp_label.add_css_class("caption")
        timestamp_label.add_css_class("dim-label")
        box.append(timestamp_label)

        # Name entry (inline editable)
        self.name_entry = Gtk.Entry()
        self.name_entry.set_text(self.item.name or "")
        self.name_entry.set_placeholder_text("Add name...")
        self.name_entry.set_width_chars(15)
        self.name_entry.set_max_width_chars(30)
        box.append(self.name_entry)

        return box
```

#### Item Content Component
**File**: `ui/components/items/item_content.py` (~120 lines)

```python
from gi.repository import Gtk, GdkPixbuf, Gdk, Pango
from models import ClipboardItem
from config import DisplaySettings
from utils import highlight_text

class ItemContent:
    """Renders item content (text/image/file)."""

    def __init__(
        self,
        item: ClipboardItem,
        settings: DisplaySettings,
        search_query: str = "",
    ):
        self.item = item
        self.settings = settings
        self.search_query = search_query

    def build(self) -> Gtk.Widget:
        """Build content widget based on item type."""
        if self.item.type == "text":
            return self._build_text_content()
        elif self.item.type == "image":
            return self._build_image_content()
        elif self.item.type == "file":
            return self._build_file_content()
        else:
            return Gtk.Label(label="Unknown content type")

    def _build_text_content(self) -> Gtk.Widget:
        """Build text content display."""
        label = Gtk.Label()
        label.set_wrap(True)
        label.set_max_width_chars(40)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        label.set_lines(6)

        # Apply highlighting if search query exists
        if self.search_query:
            markup = highlight_text(self.item.content, self.search_query)
            label.set_markup(markup)
        else:
            label.set_text(self.item.content)

        label.add_css_class("typewriter-text")
        return label

    def _build_image_content(self) -> Gtk.Widget:
        """Build image thumbnail."""
        # Implementation

    def _build_file_content(self) -> Gtk.Widget:
        """Build file info display."""
        # Implementation
```

### 3.3 Window Refactoring

#### Main Window
**File**: `ui/windows/main_window.py` (~200 lines)

```python
from gi.repository import Adw, Gtk, Gio
from core import AppContainer
from components.panels import HeaderBar, FilterBar, SearchBar
from components.lists import ClipboardList
from config import AppSettings

class MainWindow(Adw.ApplicationWindow):
    """Main application window."""

    def __init__(self, app: Adw.Application, container: AppContainer):
        super().__init__(application=app, title="TFCBM")
        self.container = container
        self.settings = container.settings

        self._setup_window()
        self._build_ui()
        self._connect_signals()

    def _setup_window(self) -> None:
        """Configure window properties."""
        window_cfg = self.settings.window
        self.set_default_size(window_cfg.default_width, window_cfg.default_height)
        self.set_resizable(True)

    def _build_ui(self) -> None:
        """Build the window UI."""
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Header
        self.header = HeaderBar(container=self.container)
        main_box.append(self.header.build())

        # Search bar
        self.search_bar = SearchBar(
            on_search=self._on_search,
            on_clear=self._on_clear_search
        )
        main_box.append(self.search_bar.build())

        # Filter bar
        self.filter_bar = FilterBar(
            container=self.container,
            on_filter_change=self._on_filter_change
        )
        main_box.append(self.filter_bar.build())

        # Main content (tabs)
        self.tab_view = self._create_tab_view()
        main_box.append(self.tab_view)

        self.set_content(main_box)

    def _create_tab_view(self) -> Gtk.Widget:
        """Create tab view with clipboard lists."""
        tab_view = Adw.TabView()

        # Copied items tab
        copied_list = ClipboardList(
            container=self.container,
            list_type="copied"
        )
        copied_page = tab_view.append(copied_list.build())
        copied_page.set_title("Recently Copied")
        copied_page.set_icon(Gio.ThemedIcon.new("edit-copy-symbolic"))

        # Pasted items tab
        pasted_list = ClipboardList(
            container=self.container,
            list_type="pasted"
        )
        pasted_page = tab_view.append(pasted_list.build())
        pasted_page.set_title("Recently Pasted")
        pasted_page.set_icon(Gio.ThemedIcon.new("edit-paste-symbolic"))

        return tab_view

    def _on_search(self, query: str) -> None:
        """Handle search."""
        # Delegate to clipboard list

    def _on_filter_change(self, filters: list) -> None:
        """Handle filter change."""
        # Delegate to clipboard list
```

---

## Phase 4: Integration (Week 5)

### 4.1 New Entry Point
**File**: `ui/main.py` (~50 lines)

```python
#!/usr/bin/env python3
"""TFCBM UI Application Entry Point."""

import sys
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from application import TFCBMApplication
from config import AppSettings, AppPaths
from core import AppContainer


def main():
    """Application entry point."""
    # Load configuration
    settings = AppSettings.load()
    paths = AppPaths.default()

    # Create dependency container
    container = AppContainer.create(settings=settings, paths=paths)

    # Create and run application
    app = TFCBMApplication(container=container)
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
```

### 4.2 Application Class
**File**: `ui/application.py` (~100 lines)

```python
from gi.repository import Adw
from core import AppContainer
from windows import MainWindow

class TFCBMApplication(Adw.Application):
    """TFCBM Application."""

    def __init__(self, container: AppContainer):
        super().__init__(application_id="com.tfcbm.app")
        self.container = container
        self.window = None

    def do_activate(self):
        """Activate the application."""
        if not self.window:
            self.window = MainWindow(self, self.container)

        self.window.present()
```

---

## Phase 5: Testing Infrastructure (Week 6)

### 5.1 Test Structure

```
tests/
├── __init__.py
├── conftest.py                      # Pytest fixtures
├── unit/
│   ├── test_services/
│   │   ├── test_clipboard_service.py
│   │   ├── test_database_service.py
│   │   ├── test_tag_service.py
│   │   └── test_pagination_service.py
│   ├── test_components/
│   │   ├── test_item_header.py
│   │   ├── test_item_content.py
│   │   └── test_filter_bar.py
│   └── test_utils/
│       ├── test_formatting.py
│       └── test_highlighting.py
└── integration/
    ├── test_clipboard_flow.py
    └── test_tag_management.py
```

### 5.2 Test Fixtures Example
**File**: `tests/conftest.py`

```python
import pytest
from pathlib import Path
from config import AppSettings, AppPaths, DisplaySettings, WindowSettings
from core import AppContainer
from services import DatabaseService

@pytest.fixture
def temp_db_path(tmp_path):
    """Temporary database path."""
    return tmp_path / "test.db"

@pytest.fixture
def test_settings():
    """Test settings."""
    return AppSettings(
        display=DisplaySettings(
            item_width=300,
            item_height=150,
            max_page_length=10
        ),
        window=WindowSettings(
            default_width=350,
            default_height=800
        )
    )

@pytest.fixture
def test_paths(tmp_path):
    """Test paths."""
    return AppPaths(
        db_path=tmp_path / "clipboard.db",
        config_path=tmp_path / "settings.yml",
        css_path=Path("style.css"),
        resources_path=Path("resouces")
    )

@pytest.fixture
def container(test_settings, test_paths):
    """Test dependency container."""
    return AppContainer.create(
        settings=test_settings,
        paths=test_paths
    )

@pytest.fixture
def db_service(temp_db_path):
    """Test database service."""
    return DatabaseService(str(temp_db_path))
```

---

## Migration Strategy

### Step-by-Step Migration

1. **Week 1: Foundation**
   - Create config system
   - Create protocols
   - Create DI container
   - **Keep old code running**

2. **Week 2: Services**
   - Complete service layer
   - Add missing services
   - Write unit tests for services
   - **Keep old code running**

3. **Week 3: Components (Part 1)**
   - Extract base components
   - Extract ItemHeader
   - Extract ItemContent
   - Extract ItemActions
   - Write component tests
   - **Keep old code running**

4. **Week 4: Components (Part 2)**
   - Extract ClipboardItemRow (using new components)
   - Extract FilterBar
   - Extract SearchBar
   - Extract panels
   - **Keep old code running**

5. **Week 5: Windows**
   - Create new MainWindow
   - Create new Application
   - Create new entry point
   - **Switch to new code, keep old as backup**

6. **Week 6: Testing & Cleanup**
   - Write integration tests
   - Remove old code
   - Final cleanup
   - Documentation

### Parallel Development Strategy

- Keep `ui/main.py` as `ui/main_old.py`
- Build new structure alongside
- Use feature flag to switch between old/new
- Gradually migrate features
- Remove old code only when new is stable

---

## Code Quality Standards

### Type Hints
```python
# Every function/method must have type hints
def process_item(item: ClipboardItem, query: str = "") -> Optional[str]:
    """Process clipboard item with optional search query.

    Args:
        item: The clipboard item to process
        query: Optional search query for highlighting

    Returns:
        Processed content string or None if processing fails
    """
```

### Docstrings
- All classes: Summary + detailed description
- All public methods: Summary + Args + Returns + Raises
- All modules: Module-level docstring

### PEP 8 Compliance
- 79 character line limit
- 4-space indentation
- 2 blank lines between classes
- 1 blank line between methods
- Import order: stdlib, third-party, local

### Linting
- **black**: Auto-formatting (79 char limit)
- **isort**: Import sorting
- **pylint**: Code quality
- **mypy**: Type checking

---

## Success Criteria

### Metrics
- ✓ No file > 300 lines
- ✓ No class > 150 lines
- ✓ No method > 30 lines
- ✓ 100% type hint coverage
- ✓ All services protocol-based
- ✓ All dependencies injected
- ✓ pylint score > 9.0
- ✓ mypy passes with --strict

### Testability
- ✓ Every component testable in isolation
- ✓ Mock all external dependencies
- ✓ No GTK required for service tests
- ✓ Fast unit tests (< 1s total)

### Maintainability
- ✓ Clear separation of concerns
- ✓ Single Responsibility Principle
- ✓ Open/Closed Principle
- ✓ Easy to add new features
- ✓ Easy to modify existing features

---

## Timeline Summary

| Week | Phase | Deliverables |
|------|-------|--------------|
| 1 | Foundation | Config system, Protocols, DI container |
| 2 | Services | All services completed and tested |
| 3 | Components Part 1 | Base components, item components |
| 4 | Components Part 2 | All UI components extracted |
| 5 | Integration | New entry point, working application |
| 6 | Testing | Full test suite, cleanup |

**Total Duration**: 6 weeks

---

## Benefits

### Immediate
- Code becomes readable and understandable
- New features easier to add
- Bugs easier to find and fix

### Medium-term
- Full test coverage possible
- Confident refactoring
- Team members can work in parallel

### Long-term
- Maintainable codebase
- Easy to onboard new developers
- Technical debt eliminated
- Foundation for future features

---

## Next Steps

1. **Review this plan** with the team
2. **Set up testing infrastructure** (pytest, fixtures)
3. **Start Phase 1** (Foundation)
4. **Regular code reviews** during refactoring
5. **Document learnings** for server refactoring

---

## Notes

- This plan focuses on **UI only**
- Server refactoring will follow similar principles
- Database module may need refactoring too
- Consider GraphQL/REST API for server communication
- Consider async/await throughout for better UX
