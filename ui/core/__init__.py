"""Core interfaces and dependency injection."""

from .di_container import AppContainer
from .protocols import (
    ClipboardPort,
    DatabasePort,
    FileServicePort,
    TagServicePort,
)

__all__ = [
    "AppContainer",
    "ClipboardPort",
    "DatabasePort",
    "FileServicePort",
    "TagServicePort",
]
