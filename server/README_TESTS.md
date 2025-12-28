# TFCBM Backend Testing Guide

## Overview

This document describes the comprehensive test suite for the TFCBM (The * Clipboard Manager) backend server. The test suite focuses on database operations, settings management, and performance testing with minimal mocking and maximum integration testing.

## Quick Start

```bash
# Run all tests (fast mode, skips slow performance tests)
.venv/bin/pytest tests/ -v -m "not slow"

# Run all tests including slow performance tests
.venv/bin/pytest tests/ -v

# Run with coverage report
.venv/bin/pytest tests/ --cov=server --cov-report=html

# Run specific test file
.venv/bin/pytest tests/database/test_clipboard_db.py -v

# Run tests matching a pattern
.venv/bin/pytest tests/ -k "test_search" -v
```

## Test Statistics

- **Total Tests**: 104
- **Pass Rate**: 100%
- **Test Duration**: ~1.25 seconds (including 1 performance test)
- **Coverage**: 78% (database.py), 83% (settings.py)

## Test Structure

```
tests/
├── conftest.py                    # Pytest configuration
├── fixtures/                      # Test fixtures and utilities
│   ├── __init__.py
│   ├── database.py               # Database fixtures (temp_db, populated_db)
│   ├── settings.py               # Settings fixtures
│   ├── test_data.py              # Test data generators
│   └── websocket.py              # WebSocket mocks (for future use)
├── database/                      # Database layer tests (57 tests)
│   ├── test_clipboard_db.py      # Core CRUD operations
│   ├── test_search_filter.py     # Search and filtering
│   ├── test_tags.py              # Tag management
│   └── test_retention.py         # Retention and secrets
├── settings/                      # Settings tests (18 tests)
│   ├── test_settings_model.py    # Pydantic model validation
│   └── test_settings_manager.py  # Settings manager
└── performance/                   # Performance tests (5 tests)
    └── test_database_performance.py
```

## Test Categories

### 1. Database Layer Tests (57 tests)

#### Core Operations (14 tests)
Tests for basic CRUD operations on clipboard items.

**File**: `tests/database/test_clipboard_db.py`

```python
# Example test
def test_add_text_item_with_metadata(temp_db):
    data = b"Hello, World!"
    item_id = temp_db.add_item("text", data)
    assert item_id > 0

    item = temp_db.get_item(item_id)
    assert item["data"] == data
```

**Covered Operations**:
- Add items (text, image, file)
- Get items by ID
- Pagination
- Update operations (timestamp, thumbnail)
- Delete operations
- Count and latest ID retrieval

#### Hash & Deduplication (7 tests)
Tests for content hashing and duplicate detection.

**Highlights**:
- SHA256 hash calculation
- Hash-based deduplication
- Large file optimization (first 64KB sampling)
- Hash lookup performance

#### Search & Filtering (10 tests)
Tests for full-text search and filtering capabilities.

**File**: `tests/database/test_search_filter.py`

**Covered Scenarios**:
- Full-text search with FTS5
- Type filtering (text, image, file)
- Multi-word search (AND logic)
- Exact phrase matching
- Secret item exclusion
- Edge cases (Unicode, emojis, special characters)

#### Tags (19 tests)
Tests for tag management and item-tag associations.

**File**: `tests/database/test_tags.py`

**Covered Operations**:
- Tag CRUD (create, read, update, delete)
- Item-tag associations
- Tag filtering (match any/all)
- Tag color management
- Cascade deletion

#### Retention & Cleanup (8 tests)
Tests for retention policy enforcement and cleanup operations.

**File**: `tests/database/test_retention.py`

**Covered Scenarios**:
- Automatic cleanup when limit exceeded
- Oldest-first deletion strategy
- Bulk deletion operations
- File extension extraction

#### Secret Items (7 tests)
Tests for secret/password item functionality.

**Highlights**:
- Secret toggle with name requirement
- Content exclusion from search
- Name-based identification
- FTS index updates

#### Edge Cases (7 tests)
Tests for boundary conditions and error handling.

**Scenarios**:
- Empty database operations
- Very long content (1MB text)
- Very long filenames (500 chars)
- Special characters and Unicode
- NULL/None handling
- Invalid IDs

### 2. Settings Tests (18 tests)

#### Model Validation (13 tests)
Tests for Pydantic model validation and serialization.

**File**: `tests/settings/test_settings_model.py`

**Covered Areas**:
- Field validation (min/max bounds)
- Default values
- Type validation
- YAML serialization/deserialization
- Custom validators

#### Settings Manager (9 tests)
Tests for settings file management.

**File**: `tests/settings/test_settings_manager.py`

**Covered Scenarios**:
- Loading from YAML files
- Missing file handling (defaults)
- Corrupted YAML handling
- Settings persistence
- Property accessors
- Settings reload

### 3. Performance Tests (5 tests)

Performance benchmarks for database operations at scale.

**File**: `tests/performance/test_database_performance.py`

**Tests** (marked as `@pytest.mark.slow`):
1. **10K Item Insertion**: Insert 10,000 items, measure throughput
2. **Search Performance**: Search across 10,000 items with FTS
3. **Pagination**: Retrieve pages from large dataset
4. **Bulk Deletion**: Delete 5,000 items at once
5. **Concurrent Reads**: Simulate concurrent read operations

**Example Performance Test**:
```python
@pytest.mark.slow
def test_insert_10000_items_performance(temp_db):
    start_time = time.time()
    for i in range(10000):
        temp_db.add_item("text", generate_random_text(50))
    elapsed = time.time() - start_time

    assert temp_db.get_total_count() == 10000
    assert elapsed < 30  # Should complete within 30 seconds
```

## Fixtures

### Database Fixtures

**`temp_db`**: In-memory SQLite database (clean slate)
```python
def test_example(temp_db):
    item_id = temp_db.add_item("text", b"test")
    assert item_id > 0
```

**`temp_db_file`**: File-based temporary database
```python
def test_example(temp_db_file):
    # Uses actual file for persistence testing
    ...
```

**`populated_db`**: Pre-populated database with sample data
- 3 text items
- 2 image items
- 1 file item

```python
def test_example(populated_db):
    # Database already has 6 items
    assert populated_db.get_total_count() == 6
```

### Settings Fixtures

**`default_settings`**: Default Settings object
**`temp_settings_file`**: Temporary YAML settings file
**`settings_manager`**: SettingsManager instance with temp file

### Test Data Generators

**Available Generators**:
- `generate_random_text(length)`: Random text strings
- `generate_random_image(width, height, format)`: Random images
- `generate_file_data(filename, content)`: File data with metadata
- `generate_timestamp(days_ago, hours_ago)`: ISO timestamps

**Example**:
```python
from tests.fixtures.test_data import generate_random_text, generate_random_image

def test_example(temp_db):
    text = generate_random_text(100)
    image = generate_random_image(200, 200, 'PNG')

    temp_db.add_item("text", text)
    temp_db.add_item("image/png", image)
```

## Testing Philosophy

### Minimal Mocking
- Tests use **real databases** (in-memory or temporary files)
- Tests use **real file I/O** (temporary YAML files)
- **No mocking** of database operations or settings
- Only external systems (DBus, WebSocket clients) are mocked

### Clean Production Code
- Production code modified to be **more testable** via dependency injection
- **No test-specific code** in production modules
- Example: Added `hash` field to `get_item()` return value for better assertions

### Test Isolation
- Each test gets a **fresh database** via fixtures
- No shared state between tests
- Tests can run in **any order**

### DRY Principles
- Reusable fixtures for common setups
- Test data generators for random content
- Shared utility functions in `fixtures/`

## Coverage Report

### Current Coverage

```
Module                      Statements    Miss    Cover
--------------------------------------------------------
server/database.py               604      131     78%
server/settings.py               107       18     83%
--------------------------------------------------------
TOTAL (tested modules)           711      149     79%
```

### Coverage Gaps

**database.py** (22% uncovered):
- Migration methods (historical, one-time operations)
- Some error handling paths
- Complex filter combinations

**settings.py** (17% uncovered):
- Error handling paths
- Some validation edge cases

## Running Tests in CI/CD

### GitHub Actions Example

```yaml
name: Backend Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.14'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install pytest pytest-cov pytest-asyncio

      - name: Run fast tests
        run: pytest tests/ -v -m "not slow" --cov=server --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
```

## Troubleshooting

### Tests Fail with Import Errors

```bash
# Ensure you're in the project root
cd /path/to/TFCBM

# Install test dependencies
.venv/bin/pip install pytest pytest-cov pytest-asyncio Pillow

# Run tests
.venv/bin/pytest tests/ -v
```

### Slow Performance Tests

Performance tests are marked with `@pytest.mark.slow`. Skip them during development:

```bash
pytest tests/ -v -m "not slow"
```

Run only performance tests:

```bash
pytest tests/ -v -m "slow"
```

### Database Locked Errors

If you see "database is locked" errors:
- Ensure tests use `temp_db` fixture (in-memory)
- Check that database connections are properly closed
- Verify no background processes are accessing test databases

## Best Practices

### Writing New Tests

1. **Use appropriate fixtures**:
   ```python
   def test_new_feature(temp_db):
       # temp_db gives you a clean database
       ...
   ```

2. **Follow naming conventions**:
   - Test files: `test_*.py`
   - Test classes: `Test*`
   - Test methods: `test_*`

3. **Use descriptive docstrings**:
   ```python
   def test_search_with_unicode(temp_db):
       """Test that search handles Unicode characters correctly."""
       ...
   ```

4. **Assert meaningfully**:
   ```python
   # Bad
   assert result

   # Good
   assert len(results) == 3, "Expected 3 search results"
   assert results[0]["type"] == "text"
   ```

5. **Use test data generators**:
   ```python
   from tests.fixtures.test_data import generate_random_text

   def test_example(temp_db):
       data = generate_random_text(100)  # Don't hardcode test data
       ...
   ```

### Debugging Failed Tests

```bash
# Run with verbose output and full tracebacks
pytest tests/ -vv --tb=long

# Run only failed tests from last run
pytest tests/ --lf

# Drop into debugger on failure
pytest tests/ --pdb

# Run specific test with print statements visible
pytest tests/database/test_clipboard_db.py::test_name -v -s
```

## Future Enhancements

From the original testing plan, these areas remain:

1. **Service Layer Tests** (planned)
   - DatabaseService thread-safety
   - WebSocketService request handling
   - ClipboardService event processing
   - ThumbnailService image processing
   - ScreenshotService capture

2. **Integration Tests** (planned)
   - Full server lifecycle
   - End-to-end flows
   - WebSocket communication
   - Multi-service interactions

3. **Error Handling Tests** (planned)
   - Database corruption recovery
   - WebSocket disconnection handling
   - Service failure scenarios

## Contributing

When adding new tests:

1. Place them in the appropriate directory (`database/`, `settings/`, etc.)
2. Use existing fixtures when possible
3. Follow the established patterns
4. Ensure tests are isolated and can run in any order
5. Add docstrings explaining what is being tested
6. Run the full suite before committing: `pytest tests/ -v`

## License

Same as TFCBM project license.
