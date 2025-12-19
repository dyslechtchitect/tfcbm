# Test Commands Quick Reference

## Run All Tests

```bash
./run_tests.sh
```

Output:
```
============================= test session starts ==============================
...
============================== 39 passed in 0.15s ==============================

✓ All tests passed!
📊 Coverage: 36% overall
```

## Run Specific Test File

```bash
./run_tests.sh tests/test_shortcut_recording.py
```

## Run Specific Test Class

```bash
./run_tests.sh tests/test_shortcut_recording.py::TestShortcutRecording
```

## Run Specific Test

```bash
./run_tests.sh tests/test_shortcut_recording.py::TestShortcutRecording::test_start_recording_mode
```

## Run Tests Matching Keyword

```bash
# Run all tests with "recording" in name
./run_tests.sh -k "recording"

# Run all tests with "observer" in name
./run_tests.sh -k "observer"

# Run all tests with "shortcut" in name
./run_tests.sh -k "shortcut"
```

## Run Tests with Different Output

```bash
# Verbose output
./run_tests.sh -v

# Very verbose (show test output)
./run_tests.sh -vv

# Short traceback
./run_tests.sh --tb=short

# No traceback
./run_tests.sh --tb=no

# Show print statements
./run_tests.sh -s
```

## Run Tests and Stop on First Failure

```bash
./run_tests.sh -x
```

## Run Tests and Enter Debugger on Failure

```bash
./run_tests.sh --pdb
```

## View Coverage Report

```bash
# HTML report (interactive)
xdg-open htmlcov/index.html

# Terminal report (already shown after tests)
./run_tests.sh

# Generate XML report (for CI)
pytest --cov=src --cov-report=xml
```

## Run Without Coverage

```bash
pytest tests/
```

## Run Tests in Parallel (if pytest-xdist installed)

```bash
pip install pytest-xdist
pytest tests/ -n auto
```

## Test Structure

```
tests/
├── test_activation_tracking.py    # 9 tests  - Activation counter
├── test_keyboard_domain.py        # 12 tests - Domain models
├── test_settings_store.py         # 7 tests  - Settings persistence
└── test_shortcut_recording.py     # 11 tests - Recording workflow
                                   ─────────
                                   39 tests total
```

## Test Naming Conventions

All tests follow this pattern:

```python
def test_<what>_<scenario>(self):
    """
    GIVEN: <initial state>
    WHEN: <action>
    THEN: <expected outcome>
    """
    # GIVEN
    # ... setup

    # WHEN
    # ... action

    # THEN
    # ... assertions
```

## Example Test Run

```bash
$ ./run_tests.sh -k "recording" -v

tests/test_shortcut_recording.py::TestShortcutRecording::test_start_recording_mode PASSED
tests/test_shortcut_recording.py::TestShortcutRecording::test_stop_recording_mode PASSED
tests/test_shortcut_recording.py::TestShortcutRecording::test_toggle_recording_mode PASSED
tests/test_shortcut_recording.py::TestShortcutRecording::test_record_shortcut_with_modifiers PASSED
tests/test_shortcut_recording.py::TestShortcutRecording::test_record_shortcut_without_modifiers PASSED
tests/test_shortcut_recording.py::TestShortcutRecording::test_ignore_modifier_only_keys PASSED
tests/test_shortcut_recording.py::TestShortcutRecording::test_ignore_key_events_when_not_recording PASSED
tests/test_shortcut_recording.py::TestShortcutObserver::test_observer_notified_on_recording PASSED
tests/test_shortcut_recording.py::TestShortcutObserver::test_observer_notified_on_apply_success PASSED
tests/test_shortcut_recording.py::TestShortcutObserver::test_observer_notified_on_apply_failure PASSED

============================== 10 passed in 0.12s ==============================
```

## Troubleshooting

### Tests fail with import errors

```bash
# Recreate virtual environment
rm -rf .venv
./run_tests.sh
```

### Coverage report not generated

```bash
# Make sure pytest-cov is installed
source .venv/bin/activate
pip install pytest-cov
./run_tests.sh
```

### Tests hang or timeout

```bash
# Check for infinite loops in code
# Add timeout to pytest
pytest tests/ --timeout=10
```

## Continuous Integration

Example GitHub Actions:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      - name: Run tests
        run: ./run_tests.sh
      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

## Development Workflow

1. **Write test first** (TDD)
   ```bash
   # Add test to tests/test_*.py
   ./run_tests.sh -k "new_test"  # Should fail
   ```

2. **Implement feature**
   ```bash
   # Add code to src/
   ./run_tests.sh -k "new_test"  # Should pass
   ```

3. **Run all tests**
   ```bash
   ./run_tests.sh  # Ensure nothing broke
   ```

4. **Check coverage**
   ```bash
   xdg-open htmlcov/index.html
   ```

## Test Coverage Goals

- **Domain Layer**: 90%+ ✅ (currently 84%)
- **Application Layer**: 85%+ ✅ (currently 88-91%)
- **Interfaces**: 80%+ ✅ (currently 80-92%)
- **Infrastructure**: Tested via fakes ✅
- **UI**: Tested via integration ✅

## Performance

```bash
# Current performance
39 tests in 0.15s = 260 tests/second

# Target: < 1s for all tests
# Current: ✅ Well under target
```

## Quick Tips

1. **Run relevant tests only** during development
   ```bash
   ./run_tests.sh -k "shortcut"
   ```

2. **Use -x to stop on first failure**
   ```bash
   ./run_tests.sh -x
   ```

3. **Use -v for more detail**
   ```bash
   ./run_tests.sh -v
   ```

4. **Check coverage for specific file**
   ```bash
   pytest --cov=src/application/shortcut_service tests/
   ```

5. **Generate coverage badge** (if desired)
   ```bash
   coverage-badge -o coverage.svg
   ```
