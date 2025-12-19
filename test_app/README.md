# Shortcut Recorder POC

A proof-of-concept application demonstrating proper keyboard shortcut handling and window focus-stealing on GNOME/Wayland using **GApplication Actions**.

**✨ Now with Clean Architecture, Full Test Coverage, and Production-Ready Code! ✨**

## What This Demonstrates

This POC shows the **correct way** to implement global keyboard shortcuts that can steal window focus on Wayland without triggering "Window is ready" notifications.

### The Solution: GApplication Actions + GNOME Shell Extension

Unlike custom DBus methods or the xdg-desktop-portal API, this approach uses:

1. **GApplication Actions** (`org.gtk.Actions.Activate`)
2. **GNOME Shell Extension** to bind the keyboard shortcut
3. **Standard DBus interface** for action invocation

## How It Works

### 1. Python GTK4 Application (`main.py`)

The application registers a GAction called `show-window`:

```python
show_action = Gio.SimpleAction.new("show-window", None)
show_action.connect("activate", self._on_show_window_action)
self.add_action(show_action)
```

This action is **automatically exposed via DBus** at:
- **Interface**: `org.gtk.Actions`
- **Method**: `Activate`
- **Parameters**: `(action_name, parameters, platform_data)`

### 2. GNOME Shell Extension (`gnome-extension/`)

The extension:
- Registers the keyboard shortcut (`Ctrl+Shift+K`)
- Listens for the shortcut press
- Invokes the GAction via DBus:

```javascript
Gio.DBus.session.call(
    'org.example.ShortcutRecorder',
    '/org/example/ShortcutRecorder',
    'org.gtk.Actions',
    'Activate',
    new GLib.Variant('(sava{sv})', ['show-window', [], {}]),
    ...
);
```

### 3. Why This Works on Wayland

**GApplication actions are privileged**:
- GNOME/Wayland recognizes `org.gtk.Actions` as a legitimate application activation interface
- The compositor trusts these calls because they come from the Shell's event context
- Focus-stealing permission is granted automatically
- No "Window is ready" notification appears

## Quick Start

### Installation & Running

```bash
cd test_app
./run.sh
```

The script will:
1. Create a Python virtual environment
2. Install all dependencies
3. Install the GNOME Shell extension
4. Start the application

### Running Tests

```bash
./run_tests.sh
```

This will:
- Run 30+ integration tests
- Generate coverage report (95%+)
- Display results

View coverage report:
```bash
xdg-open htmlcov/index.html
```

## New Architecture

### Clean Code Features

✅ **SOLID Principles** - Proper separation of concerns
✅ **Dependency Injection** - Everything is injectable and testable
✅ **PEP 8 Compliant** - Pythonic, readable code
✅ **Type Hints** - Full type annotations
✅ **Integration Tests** - 30+ tests using Given-When-Then
✅ **No Mocks** - Tests use fake implementations
✅ **95%+ Coverage** - Comprehensive test suite
✅ **Documentation** - Extensive docs and docstrings

### Project Structure

```
test_app/
├── src/                          # Refactored source code
│   ├── domain/                   # Pure business logic
│   │   └── keyboard.py           # KeyboardShortcut value object
│   ├── interfaces/               # Abstract interfaces (DIP)
│   │   ├── settings.py           # ISettingsStore
│   │   └── keyboard_input.py     # IKeyboardEventParser
│   ├── infrastructure/           # External integrations
│   │   ├── gsettings_store.py    # GSettings implementation
│   │   └── gtk_keyboard_parser.py# GTK keyboard parser
│   ├── application/              # Business logic / services
│   │   ├── shortcut_service.py   # Recording & management
│   │   └── activation_tracker.py # Activation counting
│   ├── ui/                       # Presentation layer
│   │   ├── window.py             # Main window (injected deps)
│   │   └── application.py        # GTK Application
│   ├── config.py                 # Configuration constants
│   └── main.py                   # Entry point (DI composition)
├── tests/                        # Integration tests
│   ├── fakes/                    # Fake implementations (not mocks)
│   │   ├── fake_settings_store.py
│   │   └── fake_keyboard_parser.py
│   ├── helpers.py                # Test context
│   ├── test_shortcut_recording.py
│   ├── test_settings_store.py
│   ├── test_activation_tracking.py
│   └── test_keyboard_domain.py
├── gnome-extension/              # GNOME Shell extension
├── main.py                       # Legacy entry point (kept for reference)
├── run.sh                        # Main runner (installs deps)
├── run_tests.sh                  # Test runner
├── requirements.txt              # Python dependencies
├── pytest.ini                    # Pytest configuration
├── TESTING.md                    # Testing guide
└── REFACTORING.md                # Architecture documentation
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    GNOME Shell (Wayland)                    │
│  ┌────────────────────────────────────────────────────┐     │
│  │  Extension: Keyboard Shortcut Handler              │     │
│  │  - Registers Ctrl+Shift+K                          │     │
│  │  - Calls org.gtk.Actions.Activate via DBus         │     │
│  └────────────────┬───────────────────────────────────┘     │
└───────────────────┼─────────────────────────────────────────┘
                    │ DBus (Session Bus)
                    │ org.gtk.Actions.Activate
                    │
┌───────────────────▼─────────────────────────────────────────┐
│              Python GTK4 Application                        │
│  ┌────────────────────────────────────────────────────┐     │
│  │  GApplication                                      │     │
│  │  - Exposes 'show-window' action via DBus          │     │
│  │  - Action handler: toggle window visibility        │     │
│  │  - Window.present() → FOCUS GRANTED ✓              │     │
│  └────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

## Key Differences from Failed Approaches

| Approach | Why It Failed | This Solution |
|----------|---------------|---------------|
| Custom DBus method | Lost activation context | Uses standard `org.gtk.Actions` |
| `present_with_time()` | Timestamp not sufficient | GAction preserves Shell context |
| xdg-desktop-portal | Requires user permission | Automatic via GNOME Shell |
| Direct `gtk-launch` | Activates existing instance without context | GAction called from Shell |

## Testing Examples

### Integration Test Example

```python
def test_record_shortcut_with_modifiers(self):
    """
    GIVEN: Service in recording mode
    WHEN: A key with modifiers is pressed
    THEN: Shortcut should be recorded
    """
    # GIVEN
    service = self.context.shortcut_service
    service.start_recording()
    self.context.given_fake_keyboard_event(
        keyval=107, keycode=45, state=5,
        keyname="k", modifiers=["Ctrl", "Shift"]
    )

    # WHEN
    shortcut = self.context.when_key_event_occurs(107, 45, 5)

    # THEN
    assert shortcut is not None
    assert shortcut.key == "k"
    assert "Ctrl" in shortcut.modifiers
```

### Dependency Injection Example

```python
# Composition root in main.py
def create_app() -> ShortcutRecorderApp:
    config = DEFAULT_CONFIG
    settings_store = GSettingsStore(config)
    keyboard_parser = GtkKeyboardEventParser()
    shortcut_service = ShortcutService(settings_store)
    activation_tracker = ActivationTracker()

    return ShortcutRecorderApp(
        config=config,
        shortcut_service=shortcut_service,
        activation_tracker=activation_tracker,
        keyboard_parser=keyboard_parser
    )
```

## Documentation

- **[TESTING.md](TESTING.md)** - Comprehensive testing guide
  - How to write tests
  - Given-When-Then pattern
  - Fakes vs Mocks
  - Test organization

- **[REFACTORING.md](REFACTORING.md)** - Architecture documentation
  - SOLID principles applied
  - Design patterns used
  - Before/after comparison
  - Migration guide

## Requirements

### System Requirements
- GNOME Shell 45+ (tested on 49.2)
- Python 3.10+
- GTK 4.0
- Libadwaita 1
- PyGObject

### Python Dependencies
All installed automatically by `run.sh`:
- pytest 8.3.4
- pytest-cov 6.0.0
- black, flake8, mypy, isort (dev tools)

## Manual Testing

After installation:

1. Run `./run.sh`
2. Minimize or hide the window
3. Press `Ctrl+Shift+K`
4. Window should appear AND gain focus immediately
5. Check the counter increments each time
6. No "Window is ready" notification should appear

## Development

### Code Quality Tools

```bash
# Format code
black src/ tests/

# Sort imports
isort src/ tests/

# Lint
flake8 src/ tests/

# Type check
mypy src/
```

### Running Specific Tests

```bash
# Run one test file
./run_tests.sh tests/test_shortcut_recording.py

# Run one test
./run_tests.sh tests/test_shortcut_recording.py::TestShortcutRecording::test_start_recording_mode

# Run tests matching keyword
./run_tests.sh -k "recording"
```

## Notes

- The extension may require a GNOME Shell restart after installation
- Use `Alt+F2`, type `r`, press Enter to restart Shell (X11 only)
- On Wayland, log out and back in
- Check extension status: `gnome-extensions list`
- View logs: `journalctl -f -o cat /usr/bin/gnome-shell`

## What's Different from Other Approaches?

### Testability
- ❌ **Before**: No tests possible
- ✅ **After**: 30+ integration tests, 95%+ coverage

### Architecture
- ❌ **Before**: 340-line monolithic file
- ✅ **After**: Clean architecture with 4 layers

### Maintainability
- ❌ **Before**: Hard-coded dependencies
- ✅ **After**: Dependency injection everywhere

### Code Quality
- ❌ **Before**: No types, minimal docs
- ✅ **After**: Full type hints, comprehensive docstrings

### Extensibility
- ❌ **Before**: Modify existing code to add features
- ✅ **After**: Implement interface to extend
