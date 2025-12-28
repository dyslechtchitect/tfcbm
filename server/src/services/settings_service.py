#!/usr/bin/env python3
"""
Settings Service - Wrapper for settings management
"""
import logging
from pathlib import Path
from typing import Optional

from server.src.settings import SettingsManager

logger = logging.getLogger(__name__)


class SettingsService:
    """Service for managing application settings"""

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize settings service

        Args:
            config_path: Optional path to settings file
        """
        logger.info("[SettingsService.__init__] Starting initialization...")
        logger.info(f"[SettingsService.__init__] Loading settings from: {config_path or 'default path'}")
        self._manager = SettingsManager(config_path)
        logger.info("[SettingsService.__init__] Initialization complete")

    @property
    def max_page_length(self) -> int:
        """Get maximum page length setting"""
        return self._manager.max_page_length

    @property
    def item_width(self) -> int:
        """Get item width setting"""
        return self._manager.item_width

    @property
    def item_height(self) -> int:
        """Get item height setting"""
        return self._manager.item_height

    @property
    def retention_enabled(self) -> bool:
        """Get retention enabled setting"""
        return self._manager.retention_enabled

    @property
    def retention_max_items(self) -> int:
        """Get retention max items setting"""
        return self._manager.retention_max_items

    def update_settings(self, **kwargs):
        """Update settings"""
        self._manager.update_settings(**kwargs)

    def reload(self):
        """Reload settings from file"""
        self._manager.reload()
