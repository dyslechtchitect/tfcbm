# TFCBM Logging Strategy

## Philosophy

**Clean logging principles:**
- One logger per component (injectable, testable)
- Structured output (machine-readable + human-friendly)
- Clear separation: GTK UI vs Extension vs Backend
- Easy to follow in real-time during development
- Helpful for debugging production issues

**Clarity over cleverness:**
- Simple log messages, no cryptic codes
- Include context (what, why, how much)
- Use consistent naming conventions
- Don't log secrets or PII

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Flatpak Container                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ Backend      │  │ GTK UI       │  │ DBus Service │ │
│  │ (main.py)    │  │ (ui/main.py) │  │ (dbus_*.py)  │ │
│  │              │  │              │  │              │ │
│  │ LOG_DOMAIN=  │  │ LOG_DOMAIN=  │  │ LOG_DOMAIN=  │ │
│  │ tfcbm.server │  │ tfcbm.ui     │  │ tfcbm.dbus   │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘ │
│         │                 │                  │         │
│         └─────────────────┴──────────────────┘         │
│                           │                            │
│                  systemd journal (user)                │
└───────────────────────────┼─────────────────────────────┘
                            │
┌───────────────────────────┼─────────────────────────────┐
│                    Host System (GNOME)                  │
│  ┌──────────────────────────────────────┐              │
│  │ GNOME Extension (gnome-shell)        │              │
│  │ UUID: tfcbm-clipboard-monitor@...    │              │
│  │                                      │              │
│  │ LOG_DOMAIN= tfcbm.extension          │              │
│  └──────────────┬───────────────────────┘              │
│                 │                                       │
│        systemd journal (system)                        │
└─────────────────┼───────────────────────────────────────┘
                  │
         journalctl (view all logs)
```

## Log Domains

### Backend: `tfcbm.server`
- Database operations
- IPC server connections
- Clipboard processing
- Retention/cleanup

### GTK UI: `tfcbm.ui`
- Window lifecycle
- User interactions
- IPC client communication
- Settings changes

### DBus Service: `tfcbm.dbus`
- Extension ↔ Backend communication
- Clipboard events from extension
- UI mode signals

### GNOME Extension: `tfcbm.extension`
- Panel show/hide
- Clipboard monitoring (primary)
- DBus proxy calls
- Shell integration

## Python Logging Implementation

### Clean Logger Factory (Dependency Injection)

**File:** `server/src/utils/logger.py`
```python
"""
Clean logging utilities for TFCBM.

Principles:
- One logger per component
- Injectable (easy to mock in tests)
- Structured output for systemd journal
- No global state
"""
import logging
import sys
from typing import Optional


class TFCBMLogger:
    """
    Logger factory that creates domain-scoped loggers.

    Usage:
        logger = TFCBMLogger.get_logger('tfcbm.server.database')
        logger.info("Database initialized", extra={'db_path': path, 'items': count})
    """

    _configured = False

    @classmethod
    def configure(cls, log_level: str = "INFO"):
        """
        Configure logging once at app startup.

        Args:
            log_level: DEBUG, INFO, WARNING, ERROR, CRITICAL
        """
        if cls._configured:
            return

        # Use systemd journal format (structured logging)
        # Format: TIMESTAMP LEVEL [DOMAIN] MESSAGE {key=value, ...}
        formatter = logging.Formatter(
            fmt='%(asctime)s %(levelname)-8s [%(name)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # Log to stdout (systemd captures this)
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)

        # Configure root logger
        root = logging.getLogger()
        root.setLevel(getattr(logging, log_level.upper()))
        root.addHandler(handler)

        cls._configured = True

    @staticmethod
    def get_logger(name: str) -> logging.Logger:
        """
        Get a logger for a specific component.

        Args:
            name: Logger name (e.g., 'tfcbm.server.ipc')

        Returns:
            Configured logger instance

        Example:
            logger = TFCBMLogger.get_logger('tfcbm.ui.clipboard_window')
            logger.info("Window opened")
        """
        return logging.getLogger(name)


# Convenience function for components
def get_logger(component: str) -> logging.Logger:
    """
    Get logger for a component.

    Args:
        component: Component name (e.g., 'database', 'ipc_service')
                  Will be prefixed with appropriate domain.

    Example:
        from server.src.utils.logger import get_logger
        logger = get_logger('database')
        # Creates logger named 'tfcbm.server.database'
    """
    # Auto-detect domain based on file location
    # This is set by each app's main.py
    from pathlib import Path
    caller_file = Path(__file__).parent.parent.name

    if caller_file == 'server':
        domain = 'tfcbm.server'
    elif caller_file == 'ui':
        domain = 'tfcbm.ui'
    else:
        domain = 'tfcbm'

    return TFCBMLogger.get_logger(f'{domain}.{component}')
```

### Usage in Components

**Clean, testable logging:**

```python
# server/src/services/database_service.py
from server.src.utils.logger import get_logger

class DatabaseService:
    """Database service with injectable logger"""

    def __init__(self, settings_service, logger=None):
        # Allow logger injection for testing
        self.logger = logger or get_logger('database')
        self.settings = settings_service
        self._connect()

    def _connect(self):
        """Connect to database with clear logging"""
        db_path = self.settings.database_path

        self.logger.info(
            "Connecting to database",
            extra={'db_path': db_path}
        )

        # ... connection logic ...

        item_count = self.get_total_count()
        self.logger.info(
            "Database ready",
            extra={'items': item_count, 'db_size_mb': self._get_size_mb()}
        )

    def add_item(self, item_type: str, data: bytes, timestamp: str):
        """Add item with debug logging"""
        self.logger.debug(
            "Adding item",
            extra={'type': item_type, 'size_bytes': len(data)}
        )

        # ... add logic ...

        item_id = cursor.lastrowid
        self.logger.info(
            "Item added",
            extra={'id': item_id, 'type': item_type}
        )
        return item_id
```

**Testing with mock logger:**

```python
# server/test/services/test_database_service.py
import pytest
from unittest.mock import Mock
from server.src.services.database_service import DatabaseService

def test_database_logs_connection(settings_service):
    """Verify database logs connection events"""
    mock_logger = Mock()

    db = DatabaseService(settings_service, logger=mock_logger)

    # Assert logger was called correctly
    mock_logger.info.assert_called_with(
        "Database ready",
        extra={'items': 0, 'db_size_mb': pytest.approx(0.01, abs=0.01)}
    )
```

## Extension Logging (JavaScript)

**File:** `gnome-extension/utils/logger.js`
```javascript
/**
 * Clean logging for GNOME Shell extension
 *
 * Logs to GNOME Shell journal with domain prefix.
 * Use: logger.info('Panel opened', { alignment: 'right' })
 */

const DOMAIN = 'tfcbm.extension';

/**
 * Logger class for extension components
 */
class Logger {
    constructor(component) {
        this.component = component;
        this.prefix = `[${DOMAIN}.${component}]`;
    }

    _format(level, message, context = {}) {
        const contextStr = Object.keys(context).length > 0
            ? ` ${JSON.stringify(context)}`
            : '';
        return `${this.prefix} ${level.toUpperCase()}: ${message}${contextStr}`;
    }

    debug(message, context) {
        log(this._format('debug', message, context));
    }

    info(message, context) {
        log(this._format('info', message, context));
    }

    warn(message, context) {
        logError(new Error(this._format('warn', message, context)));
    }

    error(message, error, context) {
        const msg = this._format('error', message, context);
        if (error) {
            logError(error, msg);
        } else {
            logError(new Error(msg));
        }
    }
}

/**
 * Get logger for a component
 *
 * @param {string} component - Component name (e.g., 'sidePanel', 'dbusClient')
 * @returns {Logger} Logger instance
 *
 * Example:
 *   const logger = getLogger('sidePanel');
 *   logger.info('Panel shown', { items: 5 });
 */
function getLogger(component) {
    return new Logger(component);
}
```

**Usage in extension:**

```javascript
// gnome-extension/sidePanel.js
const { getLogger } = imports.utils.logger;

class ClipboardSidePanel {
    constructor(alignment) {
        this.logger = getLogger('sidePanel');
        this.alignment = alignment;

        this.logger.info('Panel initialized', { alignment });
    }

    show() {
        this.logger.debug('Showing panel', { items: this.list.get_n_children() });
        this.actor.show();
    }

    _onItemClicked(item) {
        this.logger.info('Item clicked', { id: item.id, type: item.type });
        // ... copy logic ...
    }
}
```

## Viewing Logs

### Real-Time Development

#### Follow ALL TFCBM logs (Backend + GTK UI):
```bash
# Follow all logs from Flatpak app
journalctl --user -f -t io.github.dyslechtchitect.tfcbm

# With color highlighting
journalctl --user -f -t io.github.dyslechtchitect.tfcbm | grep --color=always -E 'INFO|DEBUG|ERROR|WARNING|$'
```

#### Follow ONLY Backend logs:
```bash
journalctl --user -f -t io.github.dyslechtchitect.tfcbm | grep '\[tfcbm.server'
```

#### Follow ONLY GTK UI logs:
```bash
journalctl --user -f -t io.github.dyslechtchitect.tfcbm | grep '\[tfcbm.ui'
```

#### Follow Extension logs:
```bash
# Extension logs to GNOME Shell's journal
journalctl -f /usr/bin/gnome-shell | grep '\[tfcbm.extension'
```

#### Follow BOTH UI modes simultaneously:
```bash
# Terminal 1: GTK UI
journalctl --user -f -t io.github.dyslechtchitect.tfcbm | grep '\[tfcbm.ui'

# Terminal 2: Extension side panel
journalctl -f /usr/bin/gnome-shell | grep '\[tfcbm.extension'
```

### Filtering by Log Level

#### Errors only:
```bash
journalctl --user -f -t io.github.dyslechtchitect.tfcbm | grep 'ERROR'
```

#### Info and above (no debug):
```bash
journalctl --user -f -t io.github.dyslechtchitect.tfcbm | grep -v 'DEBUG'
```

#### Debug level (everything):
```bash
# Set log level in settings.json or env var
flatpak run --env=TFCBM_LOG_LEVEL=DEBUG io.github.dyslechtchitect.tfcbm
```

### Post-Mortem Analysis

#### Last 100 lines:
```bash
journalctl --user -t io.github.dyslechtchitect.tfcbm -n 100
```

#### Since app restart:
```bash
journalctl --user -t io.github.dyslechtchitect.tfcbm --since "5 minutes ago"
```

#### Export logs to file:
```bash
journalctl --user -t io.github.dyslechtchitect.tfcbm --since today > tfcbm-debug.log
```

#### Search for specific events:
```bash
# Find all database operations
journalctl --user -t io.github.dyslechtchitect.tfcbm | grep '\[tfcbm.server.database\]'

# Find IPC errors
journalctl --user -t io.github.dyslechtchitect.tfcbm | grep -i 'ipc.*error'

# Find clipboard events
journalctl --user -t io.github.dyslechtchitect.tfcbm | grep 'Clipboard'
```

## Log Message Examples

### Good Logging (Clear, Contextual)

✅ **Good:**
```python
logger.info(
    "Item copied to clipboard",
    extra={'id': 42, 'type': 'text', 'size_bytes': 1024}
)
# Output: 2024-01-15 10:30:45 INFO     [tfcbm.server.clipboard] Item copied to clipboard {'id': 42, 'type': 'text', 'size_bytes': 1024}
```

✅ **Good:**
```python
logger.error(
    "Database connection failed",
    extra={'db_path': path, 'error': str(e)},
    exc_info=True
)
# Output: 2024-01-15 10:30:45 ERROR    [tfcbm.server.database] Database connection failed {'db_path': '/var/data/db.sqlite', 'error': 'Permission denied'}
#         Traceback (most recent call last): ...
```

### Bad Logging (Unclear, Missing Context)

❌ **Bad:**
```python
logger.info("Done")  # What's done? No context!
```

❌ **Bad:**
```python
logger.debug(f"Processing {item}")  # Object repr is unreadable
```

❌ **Bad:**
```python
print("ERROR: IPC failed!")  # Not using logger, hard to filter
```

❌ **Bad:**
```python
logger.info(f"Secret password: {password}")  # NEVER log secrets!
```

## Log Levels Guide

### DEBUG
**Use for:** Development troubleshooting, fine-grained tracing
**Examples:**
- Function entry/exit with parameters
- Loop iterations
- Intermediate calculation results

```python
logger.debug("Searching database", extra={'query': query, 'limit': limit})
```

### INFO
**Use for:** Normal operation milestones, user actions
**Examples:**
- App startup/shutdown
- Item copied/pasted
- Settings changed
- UI mode switched

```python
logger.info("UI mode changed", extra={'from': 'windowed', 'to': 'sidepanel'})
```

### WARNING
**Use for:** Recoverable issues, deprecation notices
**Examples:**
- Falling back to defaults
- Retrying operations
- Using deprecated features

```python
logger.warning("IPC connection lost, reconnecting...", extra={'attempt': 2})
```

### ERROR
**Use for:** Operation failures that affect functionality
**Examples:**
- Database errors
- Network failures
- Invalid user input

```python
logger.error("Failed to load item", extra={'id': item_id, 'error': str(e)})
```

### CRITICAL
**Use for:** App-breaking failures
**Examples:**
- Can't initialize database
- Missing critical dependencies
- Unrecoverable state

```python
logger.critical("Cannot start: database locked", extra={'db_path': path})
```

## Structured Logging Best Practices

### 1. Always Include Context

```python
# Bad: No context
logger.info("Request completed")

# Good: Clear context
logger.info(
    "IPC request completed",
    extra={'action': 'get_history', 'items': len(items), 'duration_ms': 42}
)
```

### 2. Use `extra` for Machine-Readable Data

```python
# This allows filtering/parsing logs programmatically
logger.info(
    "Clipboard item added",
    extra={
        'id': item_id,
        'type': item_type,
        'size_bytes': len(data),
        'has_thumbnail': thumbnail is not None
    }
)
```

### 3. Don't Log Sensitive Data

```python
# Bad: Logs password
logger.debug(f"User authenticated: {username}/{password}")

# Good: Logs fact, not secret
logger.info("User authenticated", extra={'username': username})
```

### 4. Use Consistent Naming

```python
# Always use same key names across codebase
extra={'item_id': 123}        # Good: consistent
extra={'id': 123}             # Bad: ambiguous (user id? tag id?)
extra={'clipboard_item': 123} # Bad: redundant prefix
```

## Testing Logging

### Unit Tests
```python
def test_service_logs_startup(mock_logger):
    """Verify service logs startup with correct context"""
    service = MyService(logger=mock_logger)

    mock_logger.info.assert_called_once_with(
        "Service initialized",
        extra={'component': 'MyService'}
    )
```

### Integration Tests
```python
@pytest.fixture
def captured_logs():
    """Capture logs during test"""
    import logging
    from io import StringIO

    log_stream = StringIO()
    handler = logging.StreamHandler(log_stream)
    logger = logging.getLogger('tfcbm.server')
    logger.addHandler(handler)

    yield log_stream

    logger.removeHandler(handler)

def test_database_logs_operations(captured_logs, database):
    """Verify database operations are logged"""
    database.add_item('text', b'test', '2024-01-01T00:00:00')

    logs = captured_logs.getvalue()
    assert 'Item added' in logs
    assert "'type': 'text'" in logs
```

## Environment Variables

Set log level at runtime:

```bash
# Run with debug logging
flatpak run --env=TFCBM_LOG_LEVEL=DEBUG io.github.dyslechtchitect.tfcbm

# Run with only errors
flatpak run --env=TFCBM_LOG_LEVEL=ERROR io.github.dyslechtchitect.tfcbm
```

Implementation in `main.py`:
```python
import os
from server.src.utils.logger import TFCBMLogger

# Configure logging from environment or default to INFO
log_level = os.getenv('TFCBM_LOG_LEVEL', 'INFO')
TFCBMLogger.configure(log_level)

logger = TFCBMLogger.get_logger('tfcbm.server.main')
logger.info("TFCBM server starting", extra={'log_level': log_level})
```

## Troubleshooting Common Issues

### Logs not appearing?

**Problem:** `journalctl` shows no logs from Flatpak app

**Solution:**
```bash
# Check if app is actually running
flatpak ps

# Run app in foreground to see logs directly
flatpak run io.github.dyslechtchitect.tfcbm

# Check journal for any TFCBM entries
journalctl --user --since today | grep -i tfcbm
```

### Too much noise in logs?

**Problem:** Debug logs flooding output

**Solution:**
```bash
# Filter to specific component
journalctl --user -f -t io.github.dyslechtchitect.tfcbm | grep '\[tfcbm.server.ipc\]'

# Or set log level to INFO
flatpak run --env=TFCBM_LOG_LEVEL=INFO io.github.dyslechtchitect.tfcbm
```

### Extension logs missing?

**Problem:** Can't see extension logs

**Solution:**
```bash
# Extension logs to Shell journal, not Flatpak
journalctl -f /usr/bin/gnome-shell | grep 'tfcbm'

# Check if extension is enabled
gnome-extensions list | grep tfcbm

# View extension errors
journalctl -f /usr/bin/gnome-shell | grep -i error
```

## Quick Reference Card

```bash
# Development: Watch everything
journalctl --user -f -t io.github.dyslechtchitect.tfcbm

# Backend only
journalctl --user -f -t io.github.dyslechtchitect.tfcbm | grep '\[tfcbm.server'

# GTK UI only
journalctl --user -f -t io.github.dyslechtchitect.tfcbm | grep '\[tfcbm.ui'

# Extension only
journalctl -f /usr/bin/gnome-shell | grep '\[tfcbm.extension'

# Errors only
journalctl --user -t io.github.dyslechtchitect.tfcbm | grep ERROR

# Last 50 lines
journalctl --user -t io.github.dyslechtchitect.tfcbm -n 50

# Export today's logs
journalctl --user -t io.github.dyslechtchitect.tfcbm --since today > debug.log
```

## Summary

✅ **One logger per component** - easy to filter and test
✅ **Structured logging** - machine-readable, context-rich
✅ **Clear separation** - GTK UI vs Extension vs Backend
✅ **Dependency injection** - fully testable
✅ **Easy to follow** - simple journalctl commands
✅ **Production-ready** - systemd journal integration

No clever tricks, just clean logging that works.
