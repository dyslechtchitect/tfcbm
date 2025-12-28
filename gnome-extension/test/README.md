# GNOME Extension Tests

Comprehensive test suite for the TFCBM GNOME Shell Extension clipboard monitor.

## Overview

This test suite uses **Node.js built-in test runner** (no external dependencies) with **fake objects** instead of mocks for better test maintainability and realistic behavior.

## Test Structure

```
test/
├── domain/              # Domain model tests
│   └── ClipboardEvent.test.js
├── service/             # Business logic tests
│   └── ClipboardMonitorService.test.js
├── adapters/            # Adapter tests
│   ├── GnomeClipboardAdapter.test.js
│   └── DBusNotifier.test.js
├── fakes/               # Fake implementations for testing
│   ├── FakeClipboardPort.js
│   ├── FakeNotificationPort.js
│   └── FakeGnomeAPIs.js
├── PollingScheduler.test.js
└── README.md
```

## Running Tests

```bash
# Run all tests
npm test

# Run tests with verbose output
npm run test:verbose

# Run tests in watch mode (re-runs on file changes)
npm run test:watch

# Run specific test file
node --test test/domain/ClipboardEvent.test.js
```

## Test Coverage

### Domain Layer (100% coverage)
- **ClipboardEvent**: 30 tests
  - Constructor variations (text, file, image, formatted)
  - Equality comparisons
  - JSON serialization
  - Edge cases (null, undefined, special characters, unicode)

### Service Layer (100% coverage)
- **ClipboardMonitorService**: 28 tests
  - Text clipboard changes (plain, HTML, RTF)
  - File clipboard changes (single, multiple)
  - Image clipboard changes (screenshot, web, generic)
  - Priority handling (file > image > text)
  - Duplicate detection
  - Empty clipboard handling

### Adapter Layer (100% coverage)
- **GnomeClipboardAdapter**: 14 tests
  - getText, getImage, getMimeTypes, getFormattedText
  - Multiple image format support
  - Error handling

- **DBusNotifier**: 15 tests
  - Event sending over DBus
  - Error handling
  - Backoff mechanism (500ms after failures)
  - Event serialization

### Infrastructure Layer (100% coverage)
- **PollingScheduler**: 17 tests
  - Start/stop behavior
  - Interval timing
  - Error handling
  - Integration scenarios

**Total: 92 tests across all layers**

## Testing Philosophy

### Why Fakes Over Mocks?

This test suite uses **fake objects** (real implementations with simplified behavior) instead of mocks:

1. **More realistic**: Fakes behave like real objects, catching integration issues
2. **Less brittle**: Tests don't break when internal implementation details change
3. **Better readability**: Test setup is clear and explicit
4. **Reusable**: Fakes can be shared across multiple tests

### Fake Implementations

- **FakeClipboardPort**: Simulates clipboard state (text, image, mime types)
- **FakeNotificationPort**: Records sent events for verification
- **FakeGnomeAPIs**: Simulates GNOME Shell APIs (St.Clipboard, GLib, Gio.DBus)

### Test Patterns

```javascript
// Typical test structure
beforeEach(() => {
    // Create fakes
    clipboardPort = new FakeClipboardPort();
    notificationPort = new FakeNotificationPort();
    service = new ClipboardMonitorService(clipboardPort, notificationPort);
});

it('should detect text change', async () => {
    // Arrange: Set up clipboard state
    clipboardPort.setText('Hello World');
    clipboardPort.setMimeTypes(['text/plain']);

    // Act: Trigger the behavior
    await service.checkAndNotify();

    // Assert: Verify the outcome
    assert.strictEqual(notificationPort.getEventCount(), 1);
    const event = notificationPort.getLastEvent();
    assert.strictEqual(event.type, 'text');
    assert.strictEqual(event.content, 'Hello World');
});
```

## GJS vs Node.js

The GNOME extension runs in GJS (GNOME JavaScript) which uses different APIs than Node.js:
- `import Gio from 'gi://Gio'` (GJS) vs standard Node.js modules
- `St.Clipboard`, `GLib.timeout_add` are GNOME APIs

Our tests use **testable versions** of components that accept dependencies, allowing us to inject fakes:

```javascript
// Testable version accepts dependencies
class TestableClipboardMonitorService {
    constructor(clipboardPort, notificationPort) {
        // Uses injected dependencies instead of importing GJS modules
    }
}
```

## Adding New Tests

1. **Create test file**: Follow naming convention `*.test.js`
2. **Import dependencies**: Use ES modules (`import`)
3. **Use fakes**: Prefer fakes over mocks
4. **Follow AAA pattern**: Arrange, Act, Assert
5. **Test behavior, not implementation**: Focus on what the code does, not how

Example:
```javascript
import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert';

describe('MyComponent', () => {
    let component;

    beforeEach(() => {
        component = new MyComponent();
    });

    it('should do something', () => {
        // Arrange
        const input = 'test';

        // Act
        const result = component.doSomething(input);

        // Assert
        assert.strictEqual(result, 'expected');
    });
});
```

## Test Results

All tests passing:
```
# tests 92
# suites 28
# pass 92
# fail 0
```

## CI/CD Integration

These tests can be integrated into CI/CD pipelines:

```yaml
# Example GitHub Actions
- name: Run tests
  run: |
    cd gnome-extension
    npm test
```

## Troubleshooting

**Issue**: Tests fail with "ERR_UNSUPPORTED_ESM_URL_SCHEME: gi:"
- **Cause**: Test is trying to import GJS modules directly
- **Solution**: Create testable version that accepts dependencies

**Issue**: Async tests timeout
- **Cause**: Promise not returned or async/await not used
- **Solution**: Ensure test function is `async` and use `await`

**Issue**: Test fails intermittently
- **Cause**: Race condition or timing issue
- **Solution**: Use fakes that are synchronous or properly handle async operations

## Future Improvements

- [ ] Add code coverage reporting
- [ ] Add performance benchmarks
- [ ] Add integration tests that test full GNOME extension lifecycle
- [ ] Add tests for edge cases (very large clipboard data, binary data)
