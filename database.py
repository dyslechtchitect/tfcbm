#!/usr/bin/env python3
"""
Database layer for TFCBM
Handles SQLite storage of clipboard items
"""

import hashlib
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class ClipboardDB:
    """SQLite database for clipboard items"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            # Default to ~/.local/share/tfcbm/clipboard.db
            db_dir = Path.home() / ".local" / "share" / "tfcbm"
            db_dir.mkdir(parents=True, exist_ok=True)
            db_path = db_dir / "clipboard.db"

        self.db_path = str(db_path)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()
        logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    def _init_db(self):
        """Initialize database schema"""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS clipboard_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                type TEXT NOT NULL,
                data BLOB NOT NULL,
                thumbnail BLOB,
                hash TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_timestamp
            ON clipboard_items(timestamp DESC)
        """
        )

        # Migration: Add hash column to existing databases
        cursor.execute("PRAGMA table_info(clipboard_items)")
        columns = [col[1] for col in cursor.fetchall()]
        if "hash" not in columns:
            cursor.execute("ALTER TABLE clipboard_items ADD COLUMN hash TEXT")
            logging.info("Added hash column to existing database")
            # Calculate hashes for existing non-text items
            self._migrate_calculate_hashes()

        # Create hash index (after ensuring column exists)
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_hash
            ON clipboard_items(hash)
        """
        )

        # Create recently_pasted table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS recently_pasted (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                clipboard_item_id INTEGER NOT NULL,
                pasted_timestamp TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (clipboard_item_id) REFERENCES clipboard_items(id) ON DELETE CASCADE
            )
        """
        )

        # Create index on pasted_timestamp for fast queries
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_pasted_timestamp
            ON recently_pasted(pasted_timestamp DESC)
        """
        )

        # Create index on clipboard_item_id for JOIN performance
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_clipboard_item_id
            ON recently_pasted(clipboard_item_id)
        """
        )

        self.conn.commit()
        logging.info(f"Database initialized or already exists at: {self.db_path}")

    @staticmethod
    def calculate_hash(data: bytes) -> str:
        """
        Calculate SHA256 hash of data
        Uses first 64KB for very large files for performance
        Returns hex digest (64 characters)
        """
        if len(data) > 65536:
            # For large files, hash first 64KB for performance
            data = data[:65536]
        return hashlib.sha256(data).hexdigest()

    def _migrate_calculate_hashes(self):
        """Calculate hashes for existing items without hashes"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, type, data FROM clipboard_items WHERE hash IS NULL")
        items = cursor.fetchall()

        for row in items:
            item_id, item_type, data = row["id"], row["type"], row["data"]
            hash_val = self.calculate_hash(data)
            cursor.execute("UPDATE clipboard_items SET hash = ? WHERE id = ?", (hash_val, item_id))

        if items:
            self.conn.commit()
            logging.info(f"Calculated hashes for {len(items)} existing items")

    def add_item(
        self, item_type: str, data: bytes, timestamp: str = None, thumbnail: bytes = None, data_hash: str = None
    ) -> int:
        """
        Add a clipboard item to the database

        Args:
            item_type: Type of item (text, image/png, screenshot, etc.)
            data: The actual data (text as bytes or image data)
            timestamp: ISO format timestamp (defaults to now)
            thumbnail: Optional thumbnail data for images
            data_hash: Optional pre-calculated hash (will be calculated if not provided)

        Returns:
            The ID of the inserted item
        """
        if timestamp is None:
            timestamp = datetime.now().isoformat()

        # Calculate hash if not provided (for all item types)
        if data_hash is None:
            data_hash = self.calculate_hash(data)

        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO clipboard_items (timestamp, type, data, thumbnail, hash)
            VALUES (?, ?, ?, ?, ?)
        """,
            (timestamp, item_type, data, thumbnail, data_hash),
        )
        self.conn.commit()
        item_id = cursor.lastrowid
        logging.info(
            f"Added item to DB: ID={item_id}, Type={item_type}, Hash={data_hash[:16] if data_hash else 'None'}..., Timestamp={timestamp}"
        )
        return item_id

    def hash_exists(self, data_hash: str) -> bool:
        """
        Check if a hash already exists in the database

        Args:
            data_hash: SHA256 hash to check

        Returns:
            True if hash exists, False otherwise
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM clipboard_items WHERE hash = ?", (data_hash,))
        row = cursor.fetchone()
        return row["count"] > 0

    def get_items(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """
        Get clipboard items (newest first)

        Args:
            limit: Maximum number of items to return
            offset: Number of items to skip

        Returns:
            List of items as dicts with 'id', 'timestamp', 'type', 'data', 'thumbnail'
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT id, timestamp, type, data, thumbnail
            FROM clipboard_items
            ORDER BY id DESC
            LIMIT ? OFFSET ?
        """,
            (limit, offset),
        )

        items = []
        for row in cursor.fetchall():
            items.append(
                {
                    "id": row["id"],
                    "timestamp": row["timestamp"],
                    "type": row["type"],
                    "data": row["data"],
                    "thumbnail": row["thumbnail"],
                }
            )
        return items

    def get_item(self, item_id: int) -> Optional[Dict]:
        """Get a single item by ID"""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT id, timestamp, type, data, thumbnail
            FROM clipboard_items
            WHERE id = ?
        """,
            (item_id,),
        )

        row = cursor.fetchone()
        if row:
            return {
                "id": row["id"],
                "timestamp": row["timestamp"],
                "type": row["type"],
                "data": row["data"],
                "thumbnail": row["thumbnail"],
            }
        return None

    def update_thumbnail(self, item_id: int, thumbnail: bytes) -> bool:
        """Update thumbnail for an item"""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            UPDATE clipboard_items
            SET thumbnail = ?
            WHERE id = ?
        """,
            (thumbnail, item_id),
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def delete_item(self, item_id: int) -> bool:
        """Delete an item by ID"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM clipboard_items WHERE id = ?", (item_id,))
        self.conn.commit()
        return cursor.rowcount > 0

    def clear_all(self):
        """Clear all items from database"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM clipboard_items")
        self.conn.commit()

    def get_latest_id(self) -> Optional[int]:
        """Get the ID of the most recent item"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT MAX(id) as max_id FROM clipboard_items")
        row = cursor.fetchone()
        return row["max_id"] if row["max_id"] is not None else None

    def add_pasted_item(self, clipboard_item_id: int, pasted_timestamp: str = None) -> int:
        """
        Record when a clipboard item was pasted

        Args:
            clipboard_item_id: ID of the clipboard item that was pasted
            pasted_timestamp: ISO format timestamp (defaults to now)

        Returns:
            The ID of the pasted record
        """
        if pasted_timestamp is None:
            pasted_timestamp = datetime.now().isoformat()

        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO recently_pasted (clipboard_item_id, pasted_timestamp)
            VALUES (?, ?)
        """,
            (clipboard_item_id, pasted_timestamp),
        )
        self.conn.commit()
        pasted_id = cursor.lastrowid
        logging.info(
            f"Recorded paste: Item ID={clipboard_item_id}, Pasted ID={pasted_id}, Timestamp={pasted_timestamp}"
        )
        return pasted_id

    def get_recently_pasted(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """
        Get recently pasted items (newest first) with JOIN to clipboard_items

        Args:
            limit: Maximum number of items to return
            offset: Number of items to skip

        Returns:
            List of pasted items with full clipboard item data
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT
                rp.id as paste_id,
                rp.pasted_timestamp,
                ci.id,
                ci.timestamp,
                ci.type,
                ci.data,
                ci.thumbnail
            FROM recently_pasted rp
            INNER JOIN clipboard_items ci ON rp.clipboard_item_id = ci.id
            ORDER BY rp.pasted_timestamp DESC
            LIMIT ? OFFSET ?
        """,
            (limit, offset),
        )

        items = []
        for row in cursor.fetchall():
            items.append(
                {
                    "paste_id": row["paste_id"],
                    "pasted_timestamp": row["pasted_timestamp"],
                    "id": row["id"],
                    "timestamp": row["timestamp"],
                    "type": row["type"],
                    "data": row["data"],
                    "thumbnail": row["thumbnail"],
                }
            )
        return items

    def close(self):
        """Close database connection"""
        self.conn.close()


if __name__ == "__main__":
    # Test the database
    db = ClipboardDB()
    print(f"Database initialized at: {db.db_path}")

    # Add test item
    item_id = db.add_item("text", b"Test clipboard item")
    print(f"Added item with ID: {item_id}")

    # Get items
    items = db.get_items(limit=10)
    print(f"Total items: {len(items)}")
    for item in items:
        print(f"  [{item['id']}] {item['type']}: {item['data'][:50]}")

    db.close()
