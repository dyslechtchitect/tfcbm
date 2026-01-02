"""
Clean logging utilities for TFCBM.

SOLID Principles:
- Single Responsibility: Logger factory only creates loggers
- Dependency Injection: Loggers are injectable for testing
- Clear naming: No clever tricks, obvious intent

Example:
    from server.src.utils.logger import TFCBMLogger, get_logger

    # Configure once at app startup
    TFCBMLogger.configure(log_level="INFO")

    # Get logger for component
    logger = get_logger('database')
    logger.info("Database initialized", extra={'path': db_path})
"""
import logging
import sys
from typing import Optional


class TFCBMLogger:
    """
    Logger factory that creates domain-scoped loggers.

    Usage:
        logger = TFCBMLogger.get_logger('tfcbm.server.database')
        logger.info("Database ready", extra={'items': 100})
    """

    _configured = False

    @classmethod
    def configure(cls, log_level: str = "INFO"):
        """
        Configure logging once at app startup.

        Args:
            log_level: DEBUG, INFO, WARNING, ERROR, CRITICAL

        Example:
            TFCBMLogger.configure("DEBUG")
        """
        if cls._configured:
            return

        # Systemd journal format (structured logging)
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


def get_logger(component: str, domain: str = "tfcbm.server") -> logging.Logger:
    """
    Get logger for a component (convenience function).

    Args:
        component: Component name (e.g., 'database', 'ipc_service')
        domain: Domain prefix (default: 'tfcbm.server')

    Returns:
        Logger instance

    Example:
        logger = get_logger('database')
        # Creates logger named 'tfcbm.server.database'

        logger.info("Connected", extra={'db_path': path})
    """
    return TFCBMLogger.get_logger(f'{domain}.{component}')
