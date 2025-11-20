#!/usr/bin/env python3
"""
Database layer for TFCBM
Handles SQLite storage of clipboard items
"""

import hashlib
import logging
import random
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class ClipboardDB:
    """SQLite database for clipboard items"""

    # Color palette for user-defined tags (Adwaita-inspired colors)
    TAG_COLOR_PALETTE = [
        "#3584e4",  # Blue
        "#33d17a",  # Green
        "#f6d32d",  # Yellow
        "#ff7800",  # Orange
        "#e01b24",  # Red
        "#c061cb",  # Purple
        "#9a9996",  # Gray
        "#62a0ea",  # Light Blue
        "#57e389",  # Light Green
        "#f8e45c",  # Light Yellow
        "#ffa348",  # Light Orange
        "#f66151",  # Light Red
        "#dc8add",  # Light Purple
    ]

    # System tag colors (mapped by item type)
    SYSTEM_TAG_COLORS = {
        "text": "#3584e4",  # Blue
        "image/png": "#33d17a",  # Green
        "image/jpeg": "#33d17a",  # Green
        "image/screenshot": "#e01b24",  # Red
        "image/web": "#ff7800",  # Orange
        "image/file": "#f6d32d",  # Yellow
        "image/generic": "#62a0ea",  # Light Blue
        "file": "#c061cb",  # Purple
    }

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

        # Create FTS5 virtual table for full-text search on text items
        # Use unicode61 with custom separators for better URL tokenization
        # Separators: . : / ? = & # @ (URL components)
        cursor.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS clipboard_fts
            USING fts5(content, tokenize="unicode61 separators './:?=&#@'")
            """
        )

        # Create tags table for user-defined tags
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                color TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Create item_tags junction table (many-to-many)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS item_tags (
                item_id INTEGER NOT NULL,
                tag_id INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (item_id, tag_id),
                FOREIGN KEY (item_id) REFERENCES clipboard_items(id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
            )
            """
        )

        # Create indices for tag queries
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_item_tags_item
            ON item_tags(item_id)
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_item_tags_tag
            ON item_tags(tag_id)
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
        item_id = cursor.lastrowid

        # If it's a text item, also insert into FTS for search
        if item_type == "text":
            try:
                text_content = data.decode("utf-8")
                cursor.execute(
                    """
                    INSERT INTO clipboard_fts (rowid, content)
                    VALUES (?, ?)
                    """,
                    (item_id, text_content),
                )
            except Exception as e:
                logging.warning(f"Failed to index text item {item_id} in FTS: {e}")

        self.conn.commit()
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
            List of items as dicts with 'id', 'timestamp', 'type', 'data', 'thumbnail', 'tags'
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
            item_id = row["id"]
            # Get tags for this item
            tags = self.get_tags_for_item(item_id)
            items.append(
                {
                    "id": item_id,
                    "timestamp": row["timestamp"],
                    "type": row["type"],
                    "data": row["data"],
                    "thumbnail": row["thumbnail"],
                    "tags": tags,
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

    def get_total_count(self) -> int:
        """Get total count of clipboard items"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM clipboard_items")
        row = cursor.fetchone()
        return row["count"] if row else 0

    def get_pasted_count(self) -> int:
        """Get total count of pasted items"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM recently_pasted")
        row = cursor.fetchone()
        return row["count"] if row else 0

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
            item_id = row["id"]
            # Get tags for this item
            tags = self.get_tags_for_item(item_id)
            items.append(
                {
                    "paste_id": row["paste_id"],
                    "pasted_timestamp": row["pasted_timestamp"],
                    "id": item_id,
                    "timestamp": row["timestamp"],
                    "type": row["type"],
                    "data": row["data"],
                    "thumbnail": row["thumbnail"],
                    "tags": tags,
                }
            )
        return items

    def search_items(self, query: str, limit: int = 100) -> List[Dict]:
        """
        Search clipboard items using full-text search

        Args:
            query: Search query string
            limit: Maximum number of results to return

        Returns:
            List of matching items sorted by relevance (BM25 rank)
        """
        if not query or not query.strip():
            return []

        # Escape FTS5 special characters by wrapping query in quotes
        # This treats the query as a phrase search and escapes special chars
        fts_query = f'"{query}"'

        cursor = self.conn.cursor()
        # Use FTS5 MATCH with BM25 ranking (negative rank = best matches first)
        cursor.execute(
            """
            SELECT
                ci.id,
                ci.timestamp,
                ci.type,
                ci.data,
                ci.thumbnail,
                -fts.rank as relevance
            FROM clipboard_fts fts
            INNER JOIN clipboard_items ci ON fts.rowid = ci.id
            WHERE clipboard_fts MATCH ?
            ORDER BY fts.rank
            LIMIT ?
            """,
            (fts_query, limit),
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
                    "relevance": row["relevance"],
                }
            )
        return items

    # ========== Tag Management Methods ==========

    @staticmethod
    def get_random_tag_color() -> str:
        """Get a random color from the tag color palette"""
        return random.choice(ClipboardDB.TAG_COLOR_PALETTE)

    @staticmethod
    def get_system_tag_color(item_type: str) -> str:
        """Get the system tag color for an item type"""
        return ClipboardDB.SYSTEM_TAG_COLORS.get(item_type, "#9a9996")  # Default to gray

    def create_tag(self, name: str, description: str = None, color: str = None) -> int:
        """
        Create a new tag

        Args:
            name: Tag name (must be unique)
            description: Optional tag description
            color: Optional color (hex format). If not provided, randomly selected from palette

        Returns:
            The ID of the created tag
        """
        if color is None:
            color = self.get_random_tag_color()

        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO tags (name, description, color)
                VALUES (?, ?, ?)
                """,
                (name, description, color),
            )
            self.conn.commit()
            tag_id = cursor.lastrowid
            logging.info(f"Created tag: ID={tag_id}, Name='{name}', Color={color}")
            return tag_id
        except sqlite3.IntegrityError as e:
            logging.error(f"Failed to create tag '{name}': {e}")
            raise

    def get_all_tags(self) -> List[Dict]:
        """
        Get all tags

        Returns:
            List of tags as dicts with 'id', 'name', 'description', 'color', 'created_at'
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT id, name, description, color, created_at
            FROM tags
            ORDER BY name ASC
            """
        )

        tags = []
        for row in cursor.fetchall():
            tags.append(
                {
                    "id": row["id"],
                    "name": row["name"],
                    "description": row["description"],
                    "color": row["color"],
                    "created_at": row["created_at"],
                }
            )
        return tags

    def get_tag(self, tag_id: int) -> Optional[Dict]:
        """Get a single tag by ID"""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT id, name, description, color, created_at
            FROM tags
            WHERE id = ?
            """,
            (tag_id,),
        )

        row = cursor.fetchone()
        if row:
            return {
                "id": row["id"],
                "name": row["name"],
                "description": row["description"],
                "color": row["color"],
                "created_at": row["created_at"],
            }
        return None

    def update_tag(
        self, tag_id: int, name: str = None, description: str = None, color: str = None
    ) -> bool:
        """
        Update a tag's properties

        Args:
            tag_id: ID of the tag to update
            name: New name (optional)
            description: New description (optional)
            color: New color (optional)

        Returns:
            True if tag was updated, False if not found
        """
        updates = []
        params = []

        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        if color is not None:
            updates.append("color = ?")
            params.append(color)

        if not updates:
            return False

        params.append(tag_id)
        cursor = self.conn.cursor()
        cursor.execute(
            f"""
            UPDATE tags
            SET {', '.join(updates)}
            WHERE id = ?
            """,
            params,
        )
        self.conn.commit()
        success = cursor.rowcount > 0
        if success:
            logging.info(f"Updated tag ID={tag_id}")
        return success

    def delete_tag(self, tag_id: int) -> bool:
        """
        Delete a tag by ID (also removes all item-tag associations)

        Args:
            tag_id: ID of the tag to delete

        Returns:
            True if tag was deleted, False if not found
        """
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
        self.conn.commit()
        success = cursor.rowcount > 0
        if success:
            logging.info(f"Deleted tag ID={tag_id}")
        return success

    # ========== Item-Tag Relationship Methods ==========

    def add_tag_to_item(self, item_id: int, tag_id: int) -> bool:
        """
        Add a tag to a clipboard item

        Args:
            item_id: ID of the clipboard item
            tag_id: ID of the tag

        Returns:
            True if tag was added, False if already exists
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO item_tags (item_id, tag_id)
                VALUES (?, ?)
                """,
                (item_id, tag_id),
            )
            self.conn.commit()
            logging.info(f"Added tag {tag_id} to item {item_id}")
            return True
        except sqlite3.IntegrityError:
            # Tag already exists on this item
            return False

    def remove_tag_from_item(self, item_id: int, tag_id: int) -> bool:
        """
        Remove a tag from a clipboard item

        Args:
            item_id: ID of the clipboard item
            tag_id: ID of the tag

        Returns:
            True if tag was removed, False if not found
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            DELETE FROM item_tags
            WHERE item_id = ? AND tag_id = ?
            """,
            (item_id, tag_id),
        )
        self.conn.commit()
        success = cursor.rowcount > 0
        if success:
            logging.info(f"Removed tag {tag_id} from item {item_id}")
        return success

    def get_tags_for_item(self, item_id: int) -> List[Dict]:
        """
        Get all tags associated with a clipboard item

        Args:
            item_id: ID of the clipboard item

        Returns:
            List of tags as dicts
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT t.id, t.name, t.description, t.color, t.created_at
            FROM tags t
            INNER JOIN item_tags it ON t.id = it.tag_id
            WHERE it.item_id = ?
            ORDER BY t.name ASC
            """,
            (item_id,),
        )

        tags = []
        for row in cursor.fetchall():
            tags.append(
                {
                    "id": row["id"],
                    "name": row["name"],
                    "description": row["description"],
                    "color": row["color"],
                    "created_at": row["created_at"],
                }
            )
        return tags

    def get_items_by_tags(
        self, tag_ids: List[int], match_all: bool = False, limit: int = 100, offset: int = 0
    ) -> List[Dict]:
        """
        Get clipboard items filtered by tags

        Args:
            tag_ids: List of tag IDs to filter by
            match_all: If True, items must have ALL tags. If False, items must have ANY tag.
            limit: Maximum number of items to return
            offset: Number of items to skip

        Returns:
            List of items as dicts
        """
        if not tag_ids:
            return []

        cursor = self.conn.cursor()

        if match_all:
            # Items must have ALL specified tags
            # Use HAVING COUNT to ensure item has all tags
            placeholders = ",".join("?" * len(tag_ids))
            cursor.execute(
                f"""
                SELECT ci.id, ci.timestamp, ci.type, ci.data, ci.thumbnail
                FROM clipboard_items ci
                INNER JOIN item_tags it ON ci.id = it.item_id
                WHERE it.tag_id IN ({placeholders})
                GROUP BY ci.id
                HAVING COUNT(DISTINCT it.tag_id) = ?
                ORDER BY ci.id DESC
                LIMIT ? OFFSET ?
                """,
                (*tag_ids, len(tag_ids), limit, offset),
            )
        else:
            # Items must have ANY of the specified tags
            placeholders = ",".join("?" * len(tag_ids))
            cursor.execute(
                f"""
                SELECT DISTINCT ci.id, ci.timestamp, ci.type, ci.data, ci.thumbnail
                FROM clipboard_items ci
                INNER JOIN item_tags it ON ci.id = it.item_id
                WHERE it.tag_id IN ({placeholders})
                ORDER BY ci.id DESC
                LIMIT ? OFFSET ?
                """,
                (*tag_ids, limit, offset),
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
