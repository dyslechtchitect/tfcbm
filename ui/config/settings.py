"""Application settings configuration.

NOTE: This module contains dead code - settings are actually loaded from JSON
via server/src/settings.py. This is kept for backward compatibility but not used.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class DisplaySettings:
    item_width: int = 300
    item_height: int = 150
    max_page_length: int = 50


@dataclass(frozen=True)
class WindowSettings:
    default_width: int = 350
    default_height: int = 800
    position: str = "left"


@dataclass(frozen=True)
class AppSettings:
    display: DisplaySettings
    window: WindowSettings

    @classmethod
    def load(cls, path: Optional[str] = None) -> "AppSettings":
        """Load settings - currently returns defaults (dead code)."""
        # This is dead code - actual settings are loaded from JSON
        # via server/src/settings.py
        return cls(
            display=DisplaySettings(),
            window=WindowSettings(),
        )