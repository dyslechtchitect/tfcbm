# TFCBM Coding Standards

## Philosophy

**Clarity over Cleverness**

Code is read 10x more than written. Optimize for the reader.

### SOLID Principles

1. **Single Responsibility**: One class, one reason to change
2. **Open/Closed**: Open for extension, closed for modification
3. **Liskov Substitution**: Subtypes must be substitutable
4. **Interface Segregation**: Many specific interfaces > one general
5. **Dependency Inversion**: Depend on abstractions, not concretions

### Clean Code Tenets

- **Readable**: Code should read like prose
- **Testable**: If it's hard to test, refactor it
- **Simple**: Simplest solution that works
- **No surprises**: Code does what you expect

## Python Code Style

### Dependency Injection (Testability)

✅ **Good: Injectable dependencies**
```python
class IPCService:
    """IPC service with injected dependencies"""

    def __init__(
        self,
        database_service: DatabaseService,
        settings_service: SettingsService,
        logger: logging.Logger = None
    ):
        """
        Initialize IPC service.

        Args:
            database_service: Database service instance
            settings_service: Settings service instance
            logger: Optional logger (defaults to component logger)
        """
        self.db = database_service
        self.settings = settings_service
        self.logger = logger or get_logger('ipc_service')
```

❌ **Bad: Hidden dependencies, hard to test**
```python
class IPCService:
    def __init__(self):
        # Hidden dependency - can't mock in tests!
        self.db = DatabaseService()
        self.settings = SettingsService()
        # Global logger - can't verify logging in tests!
        logging.info("IPC service started")
```

### Clear Function Signatures

✅ **Good: Type hints, clear parameters**
```python
def add_item(
    self,
    item_type: str,
    content: bytes,
    timestamp: str,
    data_hash: str = None,
    thumbnail: bytes = None
) -> int:
    """
    Add clipboard item to database.

    Args:
        item_type: Type of item (text, url, image/png, file)
        content: Item content as bytes
        timestamp: ISO 8601 timestamp
        data_hash: Optional hash for deduplication
        thumbnail: Optional thumbnail bytes

    Returns:
        int: ID of inserted item

    Raises:
        DatabaseError: If insertion fails
    """
    # Clear, self-documenting code
    if data_hash is None:
        data_hash = self._calculate_hash(content)

    item_id = self._insert_item(item_type, content, timestamp, data_hash, thumbnail)
    return item_id
```

❌ **Bad: Unclear, no types, surprise behavior**
```python
def add(self, t, c, ts, h=None, th=None):
    # What are these parameters? What does this return?
    # Side effect: also updates cache (surprise!)
    id = self.db.insert(t, c, ts, h, th)
    self.cache[id] = c  # Hidden behavior
    return id
```

### Single Responsibility

✅ **Good: One class, one job**
```python
class DatabaseService:
    """Manages SQLite database operations ONLY"""

    def add_item(self, ...): ...
    def get_item(self, ...): ...
    def delete_item(self, ...): ...


class ThumbnailService:
    """Generates thumbnails ONLY"""

    def generate_thumbnail(self, ...): ...
    def save_thumbnail(self, ...): ...


class ClipboardService:
    """Processes clipboard events ONLY"""

    def __init__(self, db: DatabaseService, thumb: ThumbnailService):
        self.db = db
        self.thumb = thumb

    def handle_clipboard_event(self, event):
        # Uses injected services, doesn't do everything itself
        item_id = self.db.add_item(...)
        thumbnail = self.thumb.generate_thumbnail(...)
        self.db.update_thumbnail(item_id, thumbnail)
```

❌ **Bad: God class doing everything**
```python
class ClipboardManager:
    """Does everything: DB, thumbnails, IPC, UI updates..."""

    def handle_clipboard(self, event):
        # Violates SRP - this class has too many reasons to change
        item_id = self._insert_to_db(...)
        thumbnail = self._generate_thumbnail(...)
        self._send_to_ipc_clients(...)
        self._update_ui(...)
        self._cleanup_old_items(...)
```

### Testable Code

✅ **Good: Easy to test**
```python
class SettingsService:
    def __init__(self, config_path: str = None):
        self.config_path = config_path or self._default_path()
        self.settings = self._load_settings()

    def _load_settings(self) -> dict:
        """Load settings from file (isolated, testable)"""
        with open(self.config_path) as f:
            return json.load(f)


# Test is simple:
def test_settings_loads_from_custom_path(tmp_path):
    config_file = tmp_path / "settings.json"
    config_file.write_text('{"ui.mode": "sidepanel"}')

    settings = SettingsService(config_path=str(config_file))

    assert settings.get('ui.mode') == 'sidepanel'
```

❌ **Bad: Hard to test (global state, no injection)**
```python
# Global config - can't override in tests!
CONFIG = load_config('/etc/tfcbm/config.json')

class SettingsService:
    def get(self, key):
        # Reads global state - every test affects every other test
        return CONFIG[key]

# Test is brittle:
def test_settings():
    # Can't isolate this test - affects global CONFIG
    # Can't run tests in parallel
    global CONFIG
    CONFIG = {'ui.mode': 'sidepanel'}  # Fragile!
    # ...
```

## JavaScript Code Style (Extension)

### Dependency Injection

✅ **Good: Injectable, testable**
```javascript
class ClipboardSidePanel {
    constructor(alignment, dbusClient = null, logger = null) {
        this.alignment = alignment;
        // Allow injection for testing
        this.dbusClient = dbusClient || new DBusClient();
        this.logger = logger || getLogger('sidePanel');
    }

    async loadHistory() {
        const items = await this.dbusClient.getHistory(0, 20);
        this._renderItems(items);
    }
}

// Test with mock:
const mockDbus = {
    getHistory: () => Promise.resolve([{ id: 1, type: 'text' }])
};
const panel = new ClipboardSidePanel('right', mockDbus);
```

❌ **Bad: Hard-coded dependencies**
```javascript
class ClipboardSidePanel {
    constructor(alignment) {
        // Can't test without real DBus connection!
        this.dbusClient = new DBusClient();
        log('Panel created');  // Global log function - can't verify
    }
}
```

### Clear Naming

✅ **Good: Self-documenting**
```javascript
class ClipboardItemWidget {
    constructor(item) {
        this.itemId = item.id;
        this.itemType = item.type;
        this.thumbnailUrl = item.thumbnail;
    }

    _buildUI() {
        this.actor = new St.BoxLayout({ vertical: false });
        this._addThumbnail();
        this._addContent();
        this._addTimestamp();
    }

    _onClicked() {
        this._copyToClipboard();
        this._hidePanel();
    }
}
```

❌ **Bad: Unclear, abbreviated**
```javascript
class CIW {  // What's CIW?
    constructor(i) {  // What's i?
        this.id = i.id;
        this.t = i.type;  // What's t?
        this.th = i.thumbnail;  // What's th?
    }

    bUI() {  // What's bUI?
        this.a = new St.BoxLayout({ vertical: false });  // What's a?
        this.aT();  // What's aT?
        this.aC();  // What's aC?
    }
}
```

## Test-Driven Development (TDD)

### Red-Green-Refactor Cycle

1. **Red**: Write failing test
2. **Green**: Write minimal code to pass
3. **Refactor**: Clean up while keeping tests green

### Example: Contract Validator

**Step 1: Red (failing test)**
```python
def test_get_history_request_validates():
    """Validator should accept valid get_history request"""
    validator = ContractValidator()

    request = {
        "action": "get_history",
        "offset": 0,
        "limit": 20
    }

    valid, error = validator.validate_request("get_history", request)

    assert valid is True
    assert error is None
```

**Step 2: Green (minimal implementation)**
```python
class ContractValidator:
    def validate_request(self, message_type, data):
        # Minimal code to pass test
        if message_type == "get_history":
            if "action" in data:
                return True, None
        return False, "Invalid request"
```

**Step 3: Refactor (clean up)**
```python
class ContractValidator:
    def __init__(self, schema_path=None):
        self.schema = self._load_schema(schema_path)

    def validate_request(self, message_type, data):
        """Validate request against schema (proper implementation)"""
        try:
            schema = self.schema['messages'][message_type]['request']
            validate(data, schema)
            return True, None
        except ValidationError as e:
            return False, str(e)
```

## Code Review Checklist

Before committing, verify:

- [ ] **SOLID**: Each class has one responsibility
- [ ] **Injectable**: Dependencies are injected, not hard-coded
- [ ] **Tested**: New code has passing tests
- [ ] **Typed**: Python functions have type hints
- [ ] **Documented**: Public APIs have docstrings
- [ ] **Logged**: Operations use injected logger
- [ ] **Clear**: Variable names are self-explanatory
- [ ] **Simple**: No clever tricks, straightforward logic
- [ ] **Flatpak-ready**: Code works inside Flatpak build

## Anti-Patterns to Avoid

### ❌ God Objects
**Problem:** One class does everything
**Solution:** Split into focused services with single responsibilities

### ❌ Hidden Dependencies
**Problem:** Classes instantiate their own dependencies
**Solution:** Inject dependencies via constructor

### ❌ Global State
**Problem:** Globals make tests fragile and non-isolated
**Solution:** Pass state explicitly, use dependency injection

### ❌ Tight Coupling
**Problem:** Classes directly reference concrete implementations
**Solution:** Depend on interfaces/protocols, inject implementations

### ❌ Untestable Code
**Problem:** Code requires real network/DB/filesystem to test
**Solution:** Inject mocks/fakes, use interfaces

### ❌ Clever Code
**Problem:** Code is concise but hard to understand
**Solution:** Write simple, readable code even if longer

## Examples of Clarity Over Cleverness

### ❌ Clever (one-liner, hard to read)
```python
items = [self.prepare(i) for i in self.db.get_items() if i['type'] in filters and not i.get('deleted')]
```

### ✅ Clear (multiple lines, obvious intent)
```python
all_items = self.db.get_items()
filtered_items = [
    item for item in all_items
    if item['type'] in filters and not item.get('deleted')
]
prepared_items = [self.prepare(item) for item in filtered_items]
```

### ❌ Clever (nested ternary, hard to parse)
```python
mode = 'sidepanel' if settings.get('ui.mode') == 'sidepanel' else 'windowed' if settings.get('ui.mode') else 'windowed'
```

### ✅ Clear (explicit logic)
```python
configured_mode = settings.get('ui.mode')
if configured_mode == 'sidepanel':
    mode = 'sidepanel'
else:
    mode = 'windowed'  # Default
```

## Summary

- **SOLID** principles guide architecture
- **Dependency injection** enables testing
- **TDD** drives development (red-green-refactor)
- **Clear naming** > clever tricks
- **Simple code** > concise code
- **Testable** always

If it's hard to test, it's wrong. Refactor it.
If it's hard to read, it's wrong. Simplify it.
If it does too much, it's wrong. Split it.

**Clarity over cleverness.**
