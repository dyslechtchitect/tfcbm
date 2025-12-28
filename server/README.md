# TFCBM Server

Backend server for The * Clipboard Manager (TFCBM).

## Project Structure

```
server/
├── src/                      # Source code
│   ├── database.py          # SQLite database layer
│   ├── dbus_service.py      # DBus integration
│   ├── settings.py          # Settings management
│   ├── settings.yml         # Settings configuration
│   └── services/            # Service modules
│       ├── clipboard_service.py
│       ├── database_service.py
│       ├── screenshot_service.py
│       ├── settings_service.py
│       ├── thumbnail_service.py
│       └── websocket_service.py
│
├── test/                    # Test suite
│   ├── integration/         # Integration tests
│   │   ├── test_database/  # Database integration tests
│   │   ├── test_settings/  # Settings integration tests
│   │   ├── performance/    # Performance benchmarks
│   │   └── fixtures/       # Test fixtures and utilities
│   └── unit/               # Unit tests (future)
│
├── pytest.ini              # Pytest configuration
├── README.md               # This file
├── README_TESTS.md         # Testing guide
└── TEST_RESULTS_SUMMARY.md # Test results summary
```

## Running Tests

From the `server/` directory:

```bash
# Run all fast tests
../.venv/bin/pytest test/integration -v -m "not slow"

# Run all tests including slow performance tests
../.venv/bin/pytest test/integration -v

# Run with coverage
../.venv/bin/pytest test/integration --cov=src --cov-report=html

# Run specific test file
../.venv/bin/pytest test/integration/test_database/test_clipboard_db.py -v
```

## Test Statistics

- **Total Tests**: 104
- **Pass Rate**: 100%
- **Test Duration**: ~1.25 seconds
- **Coverage**: 78% (database.py), 83% (settings.py)

See [README_TESTS.md](README_TESTS.md) for detailed testing documentation.

## Development

### Running the Server

```bash
cd server
python src/dbus_service.py
```

### Adding New Tests

- **Integration tests**: Place in `test/integration/`
- **Unit tests**: Place in `test/unit/` (for isolated component tests)

Follow the existing patterns in the test files and fixtures.

## Documentation

- [README_TESTS.md](README_TESTS.md) - Comprehensive testing guide
- [TEST_RESULTS_SUMMARY.md](TEST_RESULTS_SUMMARY.md) - Test execution results

## License

Same as TFCBM project license.
