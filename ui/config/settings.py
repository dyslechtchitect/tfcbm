"""Application settings configuration."""

from dataclasses import dataclass
from typing import Optional

import yaml


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
        if path is None:
            path = "settings.yml"

        config = cls._load_yaml(path)
        return cls(
            display=DisplaySettings(
                item_width=config.get("item_width", 300),
                item_height=config.get("item_height", 150),
                max_page_length=config.get("max_page_length", 50),
            ),
            window=WindowSettings(
                default_width=config.get("default_width", 350),
                default_height=config.get("default_height", 800),
                position=config.get("position", "left"),
            ),
        )

    @staticmethod
    def _load_yaml(path: str) -> dict:
        try:
            with open(path, "r") as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            return {}
        except yaml.YAMLError:
            return {}