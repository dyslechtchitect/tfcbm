# Testing Guide

## Overview

This project uses **integration tests** with **fake implementations** (not mocks) following the **Given-When-Then** pattern. The architecture is designed for testability using **dependency injection** and **SOLID principles**.

## Architecture

### Clean Architecture Layers

```
src/
├── domain/          # Pure domain logic (no dependencies)
│   └── keyboard.py  # KeyboardShortcut value object
├── interfaces/      # Abstract interfaces (dependency inversion)
│   ├── settings.py
│   └── keyboard_input.py
├── infrastructure/  # External system implementations
│   ├── gsettings_store.py
│   └── gtk_keyboard_parser.py
├── application/     # Business logic / use cases
│   ├── shortcut_service.py
│   └── activation_tracker.py
└── ui/              # Presentation layer
    ├── window.py
    └── application.py
```

### Dependency Injection

All dependencies are injected through constructors:

```python
# Bad (hard-coded dependencies)
class MyService:
    def __init__(self):
        self.store = GSettingsStore()  # ❌ Can't test with fake

# Good (injected dependencies)
class MyService:
    def __init__(self, store: ISettingsStore):
        self.store = store  # ✅ Can inject fake for testing
```

## Test Strategy

### Integration Tests (Not Unit Tests)

We use **integration tests** because:
1. Tests exercise real workflows end-to-end
2. More confidence that the system works
3. Less brittleness from implementation changes
4. Tests actual behavior, not internals

### Fakes (Not Mocks)

We use **fake implementations** instead of mocks:

```python
# Fake: Real implementation, just in-memory
class FakeSettingsStore(ISettingsStore):
    def __init__(self):
        self._shortcut = None  # Real storage, just in-memory

    def set_shortcut(self, shortcut):
        self._shortcut = shortcut  # Actually stores it
        return True

# Mock (we DON'T use these):
# mock.expect("set_shortcut").with(shortcut).returns(True)
```

**Benefits of fakes:**
- Behave like real implementations
- Can be used for multiple test scenarios
- No brittle expectations
- Test real behavior

### Given-When-Then Pattern

All tests follow this structure:

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

    # WHEN
    shortcut = self.context.when_key_event_occurs(...)

    # THEN
    assert shortcut is not None
    assert shortcut.key == "k"
```

## Running Tests

### Quick Start

```bash
# Run all tests
./run_tests.sh

# Run with specific pytest options
./run_tests.sh -v --tb=short

# Run specific test file
./run_tests.sh tests/test_shortcut_recording.py

# Run specific test
./run_tests.sh tests/test_shortcut_recording.py::TestShortcutRecording::test_start_recording_mode

# Run tests matching a keyword
./run_tests.sh -k "recording"
```

### Coverage Report

After running tests, view the coverage report:

```bash
xdg-open htmlcov/index.html
```

The report shows:
- Line coverage per file
- Branch coverage
- Missing lines

## Test Organization

### Test Files

```
tests/
├── fakes/                          # Fake implementations
│   ├── fake_settings_store.py
│   └── fake_keyboard_parser.py
├── helpers.py                      # Test context and utilities
├── test_shortcut_recording.py      # Shortcut recording tests
├── test_settings_store.py          # Settings persistence tests
├── test_activation_tracking.py     # Activation counter tests
└── test_keyboard_domain.py         # Domain model tests
```

### Test Context Helper

The `TestContext` class sets up dependencies for testing:

```python
from tests.helpers import TestContext, create_shortcut

def test_something(self):
    # Create test context with fake dependencies
    context = TestContext()

    # Setup test data
    context.given_shortcut_is_configured(
        create_shortcut(["Ctrl", "Shift"], "k")
    )

    # Exercise the system
    result = context.shortcut_service.get_current_shortcut()

    # Verify outcome
    assert result.key == "k"
```

## Writing New Tests

### 1. Use the Test Context

```python
from tests.helpers import TestContext

class TestMyFeature:
    def setup_method(self):
        self.context = TestContext()

    def test_my_scenario(self):
        # Use self.context for dependencies
        service = self.context.shortcut_service
```

### 2. Follow Given-When-Then

```python
def test_descriptive_name(self):
    """
    GIVEN: Initial state description
    WHEN: Action being tested
    THEN: Expected outcome
    """
    # GIVEN
    # ... setup

    # WHEN
    # ... action

    # THEN
    # ... assertions
```

### 3. Test Behavior, Not Implementation

```python
# Good: Tests observable behavior
def test_applying_shortcut_saves_to_settings(self):
    shortcut = create_shortcut(["Ctrl"], "k")
    self.context.shortcut_service.apply_shortcut(shortcut)
    assert self.context.settings_store.get_shortcut() == shortcut

# Bad: Tests internal implementation
def test_apply_shortcut_calls_set_method(self):
    # Don't test that methods are called
    # Test that the OUTCOME is correct
```

### 4. Use Descriptive Test Names

Test names should describe the scenario:

```python
# Good
def test_record_shortcut_with_modifiers(self):
def test_ignore_modifier_only_keys(self):
def test_observer_notified_on_recording(self):

# Bad
def test_shortcut_1(self):
def test_recording(self):
```

## Testing with Real GTK Components

To test with real GTK keyboard parser and GSettings:

```python
# Test with real GSettings (reads/writes actual settings)
context = TestContext(use_real_settings_store=True)

# Test with real GTK keyboard parser
context = TestContext(use_real_keyboard_parser=True)

# Both
context = TestContext(
    use_real_settings_store=True,
    use_real_keyboard_parser=True
)
```

**Note:** Real GSettings tests will modify your actual extension settings.

## Continuous Integration

To run tests in CI:

```yaml
# .gitlab-ci.yml or similar
test:
  script:
    - python3 -m venv .venv
    - source .venv/bin/activate
    - pip install -r requirements.txt
    - pytest --cov=src --cov-report=xml
```

## Code Quality Tools

### Black (Code Formatter)

```bash
# Format all code
black src/ tests/

# Check without modifying
black --check src/ tests/
```

### isort (Import Sorter)

```bash
# Sort imports
isort src/ tests/

# Check only
isort --check src/ tests/
```

### flake8 (Linter)

```bash
# Lint code
flake8 src/ tests/
```

### mypy (Type Checker)

```bash
# Type check
mypy src/
```

## Troubleshooting

### Tests fail with import errors

Make sure you're in the virtual environment:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### GTK import errors

Install system GTK packages:

```bash
sudo dnf install python3-gobject gtk4 libadwaita
```

### Coverage not showing all files

Make sure to run from the project root:

```bash
cd /home/ron/Documents/git/TFCBM/test_app
./run_tests.sh
```

## Best Practices

1. **One assertion per test** (when possible)
2. **Independent tests** (no test depends on another)
3. **Fast tests** (use fakes, not real I/O)
4. **Clear test names** (describes the scenario)
5. **Arrange-Act-Assert** (Given-When-Then)
6. **Test behavior** (not implementation details)
7. **Use test context** (for consistent setup)

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [Given-When-Then](https://martinfowler.com/bliki/GivenWhenThen.html)
- [Test Doubles](https://martinfowler.com/bliki/TestDouble.html)
- [Dependency Injection](https://en.wikipedia.org/wiki/Dependency_injection)
