#!/usr/bin/env python3
"""
Database Service - Wrapper for database operations
"""
import logging
import threading
from pathlib import Path
from typing import Optional, List, Dict, Any

from server.src.database import ClipboardDB

logger = logging.getLogger(__name__)


class DatabaseService:
    """Service for managing database operations with thread-safety"""

    def __init__(self, db_path: Optional[str] = None, settings_service=None):
        """
        Initialize database service

        Args:
            db_path: Optional path to database file
            settings_service: Optional settings service for retention settings
        """
        logger.info("[DatabaseService.__init__] Starting initialization...")
        logger.info(f"[DatabaseService.__init__] Connecting to database: {db_path or 'default path'}")
        self.db = ClipboardDB(db_path)
        self.lock = threading.Lock()
        self.settings_service = settings_service
        logger.info("[DatabaseService.__init__] Initializing database schema...")
        logger.info(f"Database initialized or already exists at: {self.db.db_path}")
        logger.info("[DatabaseService.__init__] Initialization complete")

    def add_item(self, item_type: str, data: bytes, timestamp: str, **kwargs) -> int:
        """Thread-safe add item to database"""
        with self.lock:
            return self.db.add_item(item_type, data, timestamp, **kwargs)

    def cleanup_old_items(self, max_items: int) -> list:
        """Thread-safe retention cleanup. Returns list of deleted item IDs."""
        with self.lock:
            return self.db.cleanup_old_items(max_items)

    def get_item(self, item_id: int) -> Optional[Dict[str, Any]]:
        """Thread-safe get item from database"""
        with self.lock:
            return self.db.get_item(item_id)

    def get_items(self, limit: int = 20, offset: int = 0, sort_order: str = "DESC",
                  filters: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """Thread-safe get items from database"""
        with self.lock:
            return self.db.get_items(limit, offset, sort_order, filters)

    def get_total_count(self) -> int:
        """Thread-safe get total item count"""
        with self.lock:
            return self.db.get_total_count()

    def get_latest_id(self) -> Optional[int]:
        """Thread-safe get latest item ID"""
        with self.lock:
            return self.db.get_latest_id()

    def get_item_by_hash(self, data_hash: str) -> Optional[int]:
        """Thread-safe check if item with hash exists"""
        with self.lock:
            return self.db.get_item_by_hash(data_hash)

    def update_timestamp(self, item_id: int, timestamp: str) -> bool:
        """Thread-safe update item timestamp"""
        with self.lock:
            return self.db.update_timestamp(item_id, timestamp)

    def update_thumbnail(self, item_id: int, thumbnail: bytes) -> bool:
        """Thread-safe update item thumbnail"""
        with self.lock:
            return self.db.update_thumbnail(item_id, thumbnail)

    def delete_item(self, item_id: int) -> bool:
        """Thread-safe delete item"""
        with self.lock:
            return self.db.delete_item(item_id)

    def get_recently_pasted(self, limit: int = 20, offset: int = 0,
                           sort_order: str = "DESC", filters: List = None) -> List[Dict[str, Any]]:
        """Thread-safe get recently pasted items"""
        with self.lock:
            return self.db.get_recently_pasted(limit, offset, sort_order, filters)

    def get_pasted_count(self) -> int:
        """Thread-safe get pasted count"""
        with self.lock:
            return self.db.get_pasted_count()

    def add_pasted_item(self, item_id: int) -> int:
        """Thread-safe record paste event"""
        with self.lock:
            return self.db.add_pasted_item(item_id)

    def search_items(self, query: str, limit: int = 100, filters: List = None) -> List[Dict[str, Any]]:
        """Thread-safe search items"""
        with self.lock:
            return self.db.search_items(query, limit, filters)

    def get_all_tags(self) -> List[Dict[str, Any]]:
        """Thread-safe get all tags"""
        with self.lock:
            return self.db.get_all_tags()

    def create_tag(self, name: str, description: str = None, color: str = None) -> int:
        """Thread-safe create tag"""
        with self.lock:
            return self.db.create_tag(name, description, color)

    def get_tag(self, tag_id: int) -> Optional[Dict[str, Any]]:
        """Thread-safe get tag"""
        with self.lock:
            return self.db.get_tag(tag_id)

    def update_tag(self, tag_id: int, name: str = None, description: str = None,
                   color: str = None) -> bool:
        """Thread-safe update tag"""
        with self.lock:
            return self.db.update_tag(tag_id, name, description, color)

    def delete_tag(self, tag_id: int) -> bool:
        """Thread-safe delete tag"""
        with self.lock:
            return self.db.delete_tag(tag_id)

    def add_tag_to_item(self, item_id: int, tag_id: int) -> bool:
        """Thread-safe add tag to item"""
        with self.lock:
            return self.db.add_tag_to_item(item_id, tag_id)

    def remove_tag_from_item(self, item_id: int, tag_id: int) -> bool:
        """Thread-safe remove tag from item"""
        with self.lock:
            return self.db.remove_tag_from_item(item_id, tag_id)

    def get_tags_for_item(self, item_id: int) -> List[Dict[str, Any]]:
        """Thread-safe get tags for item"""
        with self.lock:
            return self.db.get_tags_for_item(item_id)

    def bulk_delete_oldest(self, count: int) -> int:
        """Thread-safe bulk delete oldest items"""
        with self.lock:
            return self.db.bulk_delete_oldest(count)

    def get_items_by_tags(self, tag_ids: List[int], match_all: bool = False,
                         limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Thread-safe get items by tags"""
        with self.lock:
            return self.db.get_items_by_tags(tag_ids, match_all, limit, offset)

    def update_item_name(self, item_id: int, name: str) -> bool:
        """Thread-safe update item name"""
        with self.lock:
            return self.db.update_item_name(item_id, name)

    def toggle_secret(self, item_id: int, is_secret: bool, name: str = None) -> bool:
        """Thread-safe toggle secret status"""
        with self.lock:
            return self.db.toggle_secret(item_id, is_secret, name)

    def toggle_favorite(self, item_id: int, is_favorite: bool) -> bool:
        """Thread-safe toggle favorite status"""
        with self.lock:
            return self.db.toggle_favorite(item_id, is_favorite)

    def get_text_page(self, item_id: int, page: int = 0, page_size: int = 500) -> Optional[Dict[str, Any]]:
        """Thread-safe get a page of text content"""
        with self.lock:
            return self.db.get_text_page(item_id, page, page_size)

    def get_file_extensions(self) -> List[str]:
        """Thread-safe get file extensions"""
        with self.lock:
            return self.db.get_file_extensions()

    @staticmethod
    def calculate_hash(data: bytes) -> str:
        """Calculate hash for deduplication"""
        return ClipboardDB.calculate_hash(data)
