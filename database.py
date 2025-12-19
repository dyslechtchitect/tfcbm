#!/usr/bin/env python3
"""
Database layer for TFCBM
Handles SQLite storage of clipboard items
"""

import hashlib
import json
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
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
        )

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

        # Migration: Add name column to existing databases
        cursor.execute("PRAGMA table_info(clipboard_items)")
        columns = [col[1] for col in cursor.fetchall()]
        if "name" not in columns:
            cursor.execute("ALTER TABLE clipboard_items ADD COLUMN name TEXT")
            logging.info("Added name column to existing database")
            # Auto-populate names for files
            self._migrate_populate_file_names()

        # Migration: Add formatted text columns
        cursor.execute("PRAGMA table_info(clipboard_items)")
        columns = [col[1] for col in cursor.fetchall()]
        if "format_type" not in columns:
            cursor.execute(
                "ALTER TABLE clipboard_items ADD COLUMN format_type TEXT"
            )
            logging.info("Added format_type column to existing database")
        if "formatted_content" not in columns:
            cursor.execute(
                "ALTER TABLE clipboard_items ADD COLUMN formatted_content BLOB"
            )
            logging.info(
                "Added formatted_content column to existing database"
            )

        # Migration: Add is_secret column
        cursor.execute("PRAGMA table_info(clipboard_items)")
        columns = [col[1] for col in cursor.fetchall()]
        if "is_secret" not in columns:
            cursor.execute(
                "ALTER TABLE clipboard_items ADD COLUMN is_secret INTEGER DEFAULT 0"
            )
            logging.info("Added is_secret column to existing database")

        # Migration: Update FTS table to include name column
        # Check if FTS table needs migration by trying to query the name column
        try:
            cursor.execute("SELECT name FROM clipboard_fts LIMIT 1")
        except Exception:
            # FTS table doesn't have name column, need to rebuild
            logging.info("Migrating FTS table to include name column")
            cursor.execute("DROP TABLE IF EXISTS clipboard_fts")
            cursor.execute(
                """
                CREATE VIRTUAL TABLE clipboard_fts
                USING fts5(content, name, tokenize="unicode61 separators './:?=&#@'")
                """
            )
            # Rebuild FTS index from existing data
            cursor.execute(
                """
                INSERT INTO clipboard_fts (rowid, content, name)
                SELECT id,
                       CASE WHEN type IN ('text', 'url') THEN data ELSE '' END,
                       COALESCE(name, '')
                FROM clipboard_items
                """
            )
            logging.info("FTS table migration complete")
            self.conn.commit()

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
        logging.info(
            f"Database initialized or already exists at: {self.db_path}"
        )

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
        cursor.execute(
            "SELECT id, type, data FROM clipboard_items WHERE hash IS NULL"
        )
        items = cursor.fetchall()

        for row in items:
            item_id, item_type, data = row["id"], row["type"], row["data"]
            hash_val = self.calculate_hash(data)
            cursor.execute(
                "UPDATE clipboard_items SET hash = ? WHERE id = ?",
                (hash_val, item_id),
            )

        if items:
            self.conn.commit()
            logging.info(f"Calculated hashes for {len(items)} existing items")

    def _migrate_populate_file_names(self):
        """Auto-populate names for existing file items"""
        import json

        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, type, data FROM clipboard_items WHERE type = 'file' AND name IS NULL"
        )
        items = cursor.fetchall()

        for row in items:
            item_id, item_type, data = row["id"], row["type"], row["data"]
            # Extract filename from file metadata
            try:
                separator = b"\n---FILE_CONTENT---\n"
                if separator in data:
                    metadata_bytes, _ = data.split(separator, 1)
                    metadata = json.loads(metadata_bytes.decode("utf-8"))
                    filename = metadata.get(
                        "filename", metadata.get("name", "")
                    )
                    if filename:
                        cursor.execute(
                            "UPDATE clipboard_items SET name = ? WHERE id = ?",
                            (filename, item_id),
                        )
            except Exception as e:
                logging.warning(
                    f"Could not extract filename for item {item_id}: {e}"
                )

        if items:
            self.conn.commit()
            logging.info(
                f"Populated names for {len(items)} existing file items"
            )

    def add_item(
        self,
        item_type: str,
        data: bytes,
        timestamp: str = None,
        thumbnail: bytes = None,
        data_hash: str = None,
        name: str = None,
        format_type: str = None,
        formatted_content: bytes = None,
        is_secret: bool = False,
    ) -> int:
        """
        Add a clipboard item to the database

        Args:
            item_type: Type of item (text, image/png, screenshot, etc.)
            data: The actual data (text as bytes or image data)
            timestamp: ISO format timestamp (defaults to now)
            thumbnail: Optional thumbnail data for images
            data_hash: Optional pre-calculated hash (will be calculated if not provided)
            name: Optional custom name for the item
            format_type: Optional format type (e.g., 'html', 'rtf') for formatted text
            formatted_content: Optional formatted content (HTML, RTF, etc.)
            is_secret: Whether this item is a secret (requires name and password to view)

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
            INSERT INTO clipboard_items (timestamp, type, data, thumbnail, hash, name, format_type, formatted_content, is_secret)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                timestamp,
                item_type,
                data,
                thumbnail,
                data_hash,
                name,
                format_type,
                formatted_content,
                1 if is_secret else 0,
            ),
        )
        item_id = cursor.lastrowid

        # Insert into FTS for searchability
        # For secrets: only index name, not content
        if item_type == "text":
            try:
                # If secret, don't index content - only index name
                if is_secret:
                    text_content = ""
                else:
                    text_content = data.decode("utf-8")
                cursor.execute(
                    """
                    INSERT INTO clipboard_fts (rowid, content, name)
                    VALUES (?, ?, ?)
                    """,
                    (item_id, text_content, name if name else ""),
                )
            except Exception as e:
                logging.warning(
                    f"Failed to index text item {item_id} in FTS: {e}"
                )
        elif item_type == "file":
            # Index file items with their file name
            try:
                # Extract file name from metadata
                separator = b"\n---FILE_CONTENT---\n"
                if separator in data:
                    metadata_bytes, _ = data.split(separator, 1)
                    metadata = json.loads(metadata_bytes.decode("utf-8"))
                    file_name = metadata.get("name", "")

                    # Index with file name as content and custom name (if any)
                    cursor.execute(
                        """
                        INSERT INTO clipboard_fts (rowid, content, name)
                        VALUES (?, ?, ?)
                        """,
                        (item_id, file_name, name if name else ""),
                    )
            except Exception as e:
                logging.warning(
                    f"Failed to index file item {item_id} in FTS: {e}"
                )

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
        cursor.execute(
            "SELECT COUNT(*) as count FROM clipboard_items WHERE hash = ?",
            (data_hash,),
        )
        row = cursor.fetchone()
        return row["count"] > 0

    def get_item_by_hash(self, data_hash: str) -> Optional[int]:
        """
        Get item ID by hash

        Args:
            data_hash: SHA256 hash to look up

        Returns:
            Item ID if found, None otherwise
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id FROM clipboard_items WHERE hash = ? ORDER BY id DESC LIMIT 1",
            (data_hash,),
        )
        row = cursor.fetchone()
        return row["id"] if row else None

    def update_timestamp(
        self, item_id: int, new_timestamp: str = None
    ) -> bool:
        """
        Update the timestamp of an existing item

        Args:
            item_id: ID of the item to update
            new_timestamp: New timestamp (defaults to now)

        Returns:
            True if updated, False otherwise
        """
        if new_timestamp is None:
            new_timestamp = datetime.now().isoformat()

        cursor = self.conn.cursor()
        cursor.execute(
            """
            UPDATE clipboard_items
            SET timestamp = ?
            WHERE id = ?
            """,
            (new_timestamp, item_id),
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def get_items(
        self,
        limit: int = 100,
        offset: int = 0,
        sort_order: str = "DESC",
        filters: List[str] = None,
    ) -> List[Dict]:
        """
        Get clipboard items (sorted by timestamp)

        Args:
            limit: Maximum number of items to return
            offset: Number of items to skip
            sort_order: "DESC" for newest first, "ASC" for oldest first
            filters: List of filter strings (e.g., ["text", "image", ".pdf", "MyTag"])

        Returns:
            List of items as dicts with 'id', 'timestamp', 'type', 'data', 'thumbnail', 'tags'
        """
        cursor = self.conn.cursor()
        # Validate sort_order to prevent SQL injection
        if sort_order not in ["DESC", "ASC"]:
            sort_order = "DESC"

        # Build WHERE clause from filters
        where_clauses = []
        query_params = []

        if filters:
            # Separate filters into categories
            type_filters = []
            tag_filters = []

            for f in filters:
                if f in ["text", "image", "url", "file"]:
                    # Content type filters
                    if f == "text":
                        type_filters.append("type = 'text'")
                    elif f == "image":
                        type_filters.append(
                            "(type LIKE 'image/%' OR type = 'screenshot')"
                        )
                    elif f == "url":
                        type_filters.append("type = 'url'")
                    elif f == "file":
                        type_filters.append("type = 'file'")
                elif f.startswith("file:"):
                    # File extension filter (format: "file:pdf", "file:docx", etc.)
                    ext = f[5:]  # Remove "file:" prefix
                    type_filters.append("type LIKE ?")
                    query_params.append(f"%{ext}%")
                elif f.startswith("."):
                    # File extension filter (format: ".pdf", ".docx", etc.)
                    type_filters.append("type LIKE ?")
                    query_params.append(f"%{f}%")
                else:
                    # Custom tag filter
                    tag_filters.append(f)

            # Combine type filters with OR
            if type_filters:
                where_clauses.append(f"({' OR '.join(type_filters)})")

            # Handle tag filters
            if tag_filters:
                # Build subquery for tags
                tag_placeholders = ",".join("?" * len(tag_filters))
                where_clauses.append(
                    f"""id IN (
                    SELECT item_id FROM item_tags
                    WHERE tag_id IN (
                        SELECT id FROM tags WHERE name IN ({tag_placeholders})
                    )
                )"""
                )
                query_params.extend(tag_filters)

        # Build final query
        where_clause = ""
        if where_clauses:
            where_clause = "WHERE " + " AND ".join(where_clauses)

        query = f"""
            SELECT id, timestamp, type, data, thumbnail, name, format_type, formatted_content, is_secret
            FROM clipboard_items
            {where_clause}
            ORDER BY timestamp {sort_order}
            LIMIT ? OFFSET ?
        """

        query_params.extend([limit, offset])

        # Debug logging
        import logging

        logging.info(f"[FILTER DB] Filters: {filters}")
        logging.info(f"[FILTER DB] WHERE clause: {where_clause}")
        logging.info(f"[FILTER DB] Query params: {query_params}")

        cursor.execute(query, tuple(query_params))

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
                    "name": row["name"],
                    "format_type": row["format_type"],
                    "formatted_content": row["formatted_content"],
                    "is_secret": bool(row["is_secret"]),
                    "tags": tags,
                }
            )
        return items

    def get_item(self, item_id: int) -> Optional[Dict]:
        """Get a single item by ID"""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT id, timestamp, type, data, thumbnail, name, format_type, formatted_content, is_secret
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
                "name": row["name"],
                "format_type": row["format_type"],
                "formatted_content": row["formatted_content"],
                "is_secret": bool(row["is_secret"]),
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
        # Delete from FTS first (if exists)
        try:
            cursor.execute(
                "DELETE FROM clipboard_fts WHERE rowid = ?", (item_id,)
            )
        except Exception as e:
            logging.warning(
                f"Failed to delete FTS entry for item {item_id}: {e}"
            )
        # Delete from main table
        cursor.execute("DELETE FROM clipboard_items WHERE id = ?", (item_id,))
        self.conn.commit()
        return cursor.rowcount > 0

    def update_item_name(self, item_id: int, name: str) -> bool:
        """Update the name of an item"""
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE clipboard_items SET name = ? WHERE id = ?",
            (name if name else None, item_id),
        )

        # Also update FTS table.
        # We need to get the item's content to potentially re-insert/update FTS.
        cursor.execute(
            "SELECT type, data, is_secret FROM clipboard_items WHERE id = ?", (item_id,)
        )
        row = cursor.fetchone()
        if row:
            item_type = row["type"]
            item_data = row["data"]
            is_secret = bool(row["is_secret"])

            fts_content = ""
            if item_type == "text" and not is_secret: # Only index text content if not secret
                fts_content = item_data.decode("utf-8")
            elif item_type == "file":
                # Extract filename from file metadata
                separator = b"\n---FILE_CONTENT---\n"
                if separator in item_data:
                    metadata_bytes, _ = item_data.split(separator, 1)
                    metadata = json.loads(metadata_bytes.decode("utf-8"))
                    fts_content = metadata.get("name", "") # Index file name as content

            try:
                # Use INSERT OR REPLACE to update or insert the FTS entry
                cursor.execute(
                    "INSERT OR REPLACE INTO clipboard_fts (rowid, content, name) VALUES (?, ?, ?)",
                    (item_id, fts_content, name if name else ""),
                )
            except Exception as e:
                logging.warning(
                    f"Failed to update FTS for item {item_id} with name '{name}': {e}"
                )

        self.conn.commit()
        return cursor.rowcount > 0

    def toggle_secret(self, item_id: int, is_secret: bool, name: str = None) -> bool:
        """
        Toggle the secret status of an item

        Args:
            item_id: ID of the item to toggle
            is_secret: Whether the item should be a secret
            name: Optional name to set (required if marking as secret and item has no name)

        Returns:
            True if successful, False otherwise
        """
        cursor = self.conn.cursor()

        # If marking as secret, require a name
        if is_secret:
            cursor.execute(
                "SELECT name FROM clipboard_items WHERE id = ?", (item_id,)
            )
            row = cursor.fetchone()
            if row:
                current_name = row["name"]
                # If no name provided and item has no name, return False
                if not name and not current_name:
                    return False
                # Update name if provided
                if name:
                    cursor.execute(
                        "UPDATE clipboard_items SET name = ? WHERE id = ?",
                        (name, item_id),
                    )

        # Update is_secret status
        cursor.execute(
            "UPDATE clipboard_items SET is_secret = ? WHERE id = ?",
            (1 if is_secret else 0, item_id),
        )

        # Update FTS: remove content if making secret, restore if unmarking
        cursor.execute(
            "SELECT type, data, name FROM clipboard_items WHERE id = ?", (item_id,)
        )
        row = cursor.fetchone()
        if row: # Make sure the item exists
            item_type = row["type"]
            item_data = row["data"]
            # Use the current name from clipboard_items (which was just updated if name was provided)
            item_name = row["name"] if row["name"] else ""

            fts_content = ""
            if item_type == "text" and not is_secret:
                fts_content = item_data.decode("utf-8")
            elif item_type == "file" and not is_secret: # Files also have content, but only name is indexed
                 # Extract filename from file metadata
                separator = b"\n---FILE_CONTENT---\n"
                if separator in item_data:
                    metadata_bytes, _ = item_data.split(separator, 1)
                    metadata = json.loads(metadata_bytes.decode("utf-8"))
                    fts_content = metadata.get("name", "") # Index file name as content

            try:
                cursor.execute(
                    "INSERT OR REPLACE INTO clipboard_fts (rowid, content, name) VALUES (?, ?, ?)",
                    (item_id, fts_content, item_name),
                )
            except Exception as e:
                logging.warning(
                    f"Failed to update FTS content for item {item_id}: {e}"
                )

        self.conn.commit()
        return True

    def clear_all(self):
        """Clear all items from database"""
        cursor = self.conn.cursor()
        # Clear FTS table first
        try:
            cursor.execute("DELETE FROM clipboard_fts")
        except Exception as e:
            logging.warning(f"Failed to clear FTS table: {e}")
        # Clear main table
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

    def add_pasted_item(
        self, clipboard_item_id: int, pasted_timestamp: str = None
    ) -> int:
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

    def get_recently_pasted(
        self, limit: int = 100, offset: int = 0, sort_order: str = "DESC", filters: List[str] = None
    ) -> List[Dict]:
        """
        Get recently pasted items (sorted by pasted timestamp) with JOIN to clipboard_items

        Args:
            limit: Maximum number of items to return
            offset: Number of items to skip
            sort_order: "DESC" for newest first, "ASC" for oldest first
            filters: List of filter strings (e.g., ["text", "image", "url", "file", "MyTag"])

        Returns:
            List of pasted items with full clipboard item data
        """
        cursor = self.conn.cursor()
        # Validate sort_order to prevent SQL injection
        if sort_order not in ["DESC", "ASC"]:
            sort_order = "DESC"

        # Build WHERE clause from filters (same logic as get_items)
        where_clauses = []
        query_params = []

        if filters:
            # Separate filters into categories
            type_filters = []
            tag_filters = []

            for f in filters:
                if f in ["text", "image", "url", "file"]:
                    # Content type filters
                    if f == "text":
                        type_filters.append("ci.type = 'text'")
                    elif f == "image":
                        type_filters.append(
                            "(ci.type LIKE 'image/%' OR ci.type = 'screenshot')"
                        )
                    elif f == "url":
                        type_filters.append("ci.type = 'url'")
                    elif f == "file":
                        type_filters.append("ci.type = 'file'")
                elif f.startswith("file:"):
                    # File extension filter (format: "file:pdf", "file:docx", etc.)
                    ext = f[5:]  # Remove "file:" prefix
                    type_filters.append("ci.type LIKE ?")
                    query_params.append(f"%{ext}%")
                elif f.startswith("."):
                    # File extension filter (format: ".pdf", ".docx", etc.)
                    type_filters.append("ci.type LIKE ?")
                    query_params.append(f"%{f}%")
                else:
                    # Custom tag filter
                    tag_filters.append(f)

            # Combine type filters with OR
            if type_filters:
                where_clauses.append(f"({' OR '.join(type_filters)})")

            # Handle tag filters
            if tag_filters:
                # Build subquery for tags
                tag_placeholders = ",".join("?" * len(tag_filters))
                where_clauses.append(
                    f"""ci.id IN (
                    SELECT item_id FROM item_tags
                    WHERE tag_id IN (
                        SELECT id FROM tags WHERE name IN ({tag_placeholders})
                    )
                )"""
                )
                query_params.extend(tag_filters)

        # Build final query
        where_clause = ""
        if where_clauses:
            where_clause = "WHERE " + " AND ".join(where_clauses)

        query = f"""
            SELECT
                rp.id as paste_id,
                rp.pasted_timestamp,
                ci.id,
                ci.timestamp,
                ci.type,
                ci.data,
                ci.thumbnail,
                ci.name,
                ci.format_type,
                ci.formatted_content,
                ci.is_secret
            FROM recently_pasted rp
            INNER JOIN clipboard_items ci ON rp.clipboard_item_id = ci.id
            {where_clause}
            ORDER BY rp.pasted_timestamp {sort_order}
            LIMIT ? OFFSET ?
        """

        query_params.extend([limit, offset])

        # Debug logging
        import logging
        logging.info(f"[FILTER DB PASTED] Filters: {filters}")
        logging.info(f"[FILTER DB PASTED] WHERE clause: {where_clause}")
        logging.info(f"[FILTER DB PASTED] Query params: {query_params}")

        cursor.execute(query, tuple(query_params))

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
                    "name": row["name"],
                    "format_type": row["format_type"],
                    "formatted_content": row["formatted_content"],
                    "is_secret": bool(row["is_secret"]),
                    "tags": tags,
                }
            )
        return items

    def search_items(
        self, query: str, limit: int = 100, filters: List[str] = None
    ) -> List[Dict]:
        """
        Search clipboard items using full-text search

        Args:
            query: Search query string
            limit: Maximum number of results to return
            filters: List of filter strings (e.g., ["text", "image", "file:pdf", "MyTag"])

        Returns:
            List of matching items sorted by relevance (BM25 rank)
        """
        if not query or not query.strip():
            return []

        # Build FTS5 query:
        # - If user wraps in quotes: exact phrase search
        # - Multiple words without quotes: ALL words must appear (AND), any order
        # - FTS5 BM25 ranks by relevance (more occurrences = higher score)

        query = query.strip()

        # Check if user wrapped entire query in quotes for exact phrase
        if query.startswith('"') and query.endswith('"'):
            # User wants exact phrase - use as-is
            fts_query = query
        else:
            # Parse query: respect quoted phrases but split unquoted words
            # Example: hello "world foo" bar → hello AND "world foo" AND bar
            import re
            # Split on spaces but keep quoted phrases together
            parts = re.findall(r'"[^"]+"|\S+', query)

            # Wrap non-quoted words in quotes to escape special chars
            fts_parts = []
            for part in parts:
                if part.startswith('"') and part.endswith('"'):
                    # Already quoted phrase
                    fts_parts.append(part)
                else:
                    # Individual word - quote it
                    fts_parts.append(f'"{part}"')

            # Join with spaces (FTS5 treats space-separated terms as AND by default)
            fts_query = " ".join(fts_parts)

        # Build filter conditions for both FTS and tag queries
        type_filter_clause = ""
        tag_filter_clause = ""
        filter_params = []

        if filters:
            # Separate filters into categories
            type_filters = []
            tag_filters = []

            for f in filters:
                if f in ["text", "image", "url", "file"]:
                    # Content type filters
                    if f == "text":
                        type_filters.append("ci.type = 'text'")
                    elif f == "image":
                        type_filters.append(
                            "(ci.type LIKE 'image/%' OR ci.type = 'screenshot')"
                        )
                    elif f == "url":
                        type_filters.append("ci.type = 'url'")
                    elif f == "file":
                        type_filters.append("ci.type = 'file'")
                elif f.startswith("file:"):
                    # File extension filter (format: "file:pdf", "file:docx", etc.)
                    ext = f[5:]  # Remove "file:" prefix
                    type_filters.append("ci.type LIKE ?")
                    filter_params.append(f"%{ext}%")
                elif f.startswith("."):
                    # File extension filter (format: ".pdf", ".docx", etc.)
                    type_filters.append("ci.type LIKE ?")
                    filter_params.append(f"%{f}%")
                else:
                    # Custom tag filter
                    tag_filters.append(f)

            # Combine type filters with OR
            if type_filters:
                type_filter_clause = f" AND ({' OR '.join(type_filters)})"

            # Handle tag filters
            if tag_filters:
                # Build subquery for tags
                tag_placeholders = ",".join("?" * len(tag_filters))
                tag_filter_clause = f""" AND ci.id IN (
                    SELECT item_id FROM item_tags
                    WHERE tag_id IN (
                        SELECT id FROM tags WHERE name IN ({tag_placeholders})
                    )
                )"""
                filter_params.extend(tag_filters)

        # Debug logging
        import logging

        logging.info(f"[SEARCH DB] Query: '{query}', Filters: {filters}")

        cursor = self.conn.cursor()

        # Use UNION to combine FTS results with tag-based results
        # Query 1: FTS search (content and names)
        # Query 2: Tag name search
        query_sql = f"""
            SELECT DISTINCT
                ci.id,
                ci.timestamp,
                ci.type,
                ci.data,
                ci.thumbnail,
                ci.name,
                ci.format_type,
                ci.formatted_content,
                ci.is_secret,
                -rank as relevance
            FROM clipboard_fts
            INNER JOIN clipboard_items ci ON clipboard_fts.rowid = ci.id
            WHERE clipboard_fts MATCH ?{type_filter_clause}{tag_filter_clause}
            ORDER BY relevance, timestamp DESC
            LIMIT ?
        """

        # Build parameter list: fts_query, filter_params (once), limit
        query_params = [fts_query] + filter_params + [limit]

        logging.info(f"[SEARCH DB] SQL: {query_sql}")
        logging.info(f"[SEARCH DB] Params: {query_params}")

        cursor.execute(query_sql, tuple(query_params))

        items = []
        for row in cursor.fetchall():
            items.append(
                {
                    "id": row["id"],
                    "timestamp": row["timestamp"],
                    "type": row["type"],
                    "data": row["data"],
                    "thumbnail": row["thumbnail"],
                    "name": row["name"],
                    "format_type": row["format_type"],
                    "formatted_content": row["formatted_content"],
                    "is_secret": bool(row["is_secret"]),
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
        return ClipboardDB.SYSTEM_TAG_COLORS.get(
            item_type, "#9a9996"
        )  # Default to gray

    def create_tag(
        self, name: str, description: str = None, color: str = None
    ) -> int:
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
            logging.info(
                f"Created tag: ID={tag_id}, Name='{name}', Color={color}"
            )
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
        self,
        tag_id: int,
        name: str = None,
        description: str = None,
        color: str = None,
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

            # NEW: Update FTS for this item to include the new tag's name
            tag = self.get_tag(tag_id)
            if tag:
                tag_name = tag.get("name", "")
                # Get current FTS content and name for this item
                cursor.execute("SELECT content, name FROM clipboard_fts WHERE rowid = ?", (item_id,))
                fts_row = cursor.fetchone()
                if fts_row:
                    current_fts_content = fts_row["content"]
                    current_fts_name = fts_row["name"]
                    # Append new tag name to FTS name field, avoid duplicates
                    new_fts_name_parts = set(current_fts_name.split())
                    new_fts_name_parts.add(tag_name)
                    new_fts_name = " ".join(list(new_fts_name_parts))
                    cursor.execute(
                        """
                        UPDATE clipboard_fts
                        SET name = ?
                        WHERE rowid = ?
                        """,
                        (new_fts_name, item_id),
                    )
                    self.conn.commit()
                    logging.info(f"Updated FTS for item {item_id} with tag '{tag_name}'")
                else:
                    # If item not in FTS (e.g., image), insert it with tag name
                    # We need to get content for this item
                    item = self.get_item(item_id)
                    if item:
                        item_content = item.get("data", b"").decode("utf-8") if item.get("type") == "text" else ""
                        cursor.execute(
                            """
                            INSERT INTO clipboard_fts (rowid, content, name)
                            VALUES (?, ?, ?)
                            """,
                            (item_id, item_content, tag_name),
                        )
                        self.conn.commit()
                        logging.info(f"Inserted item {item_id} into FTS with tag '{tag_name}'")


            logging.info(f"Committed add tag {tag_id} to item {item_id}")
            return True
        except sqlite3.IntegrityError:
            # Tag already exists on this item
            logging.warning(f"Tag {tag_id} already exists on item {item_id}")
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
            # NEW: Update FTS for this item to remove the tag's name
            tag = self.get_tag(tag_id)
            if tag:
                tag_name = tag.get("name", "")
                cursor.execute("SELECT content, name FROM clipboard_fts WHERE rowid = ?", (item_id,))
                fts_row = cursor.fetchone()
                if fts_row:
                    current_fts_content = fts_row["content"]
                    current_fts_name = fts_row["name"]
                    # Remove tag name from FTS name field
                    new_fts_name_parts = [p for p in current_fts_name.split() if p != tag_name]
                    new_fts_name = " ".join(new_fts_name_parts)
                    cursor.execute(
                        """
                        UPDATE clipboard_fts
                        SET name = ?
                        WHERE rowid = ?
                        """,
                        (new_fts_name, item_id),
                    )
                    self.conn.commit()
                    logging.info(f"Updated FTS for item {item_id} by removing tag '{tag_name}'")

            logging.info(f"Committed remove tag {tag_id} from item {item_id}")
        else:
            logging.warning(
                f"Attempted to remove non-existent tag {tag_id} from item {item_id}"
            )
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
        self,
        tag_ids: List[int],
        match_all: bool = False,
        limit: int = 100,
        offset: int = 0,
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
                SELECT ci.id, ci.timestamp, ci.type, ci.data, ci.thumbnail, ci.name, ci.format_type, ci.formatted_content, ci.is_secret
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
                SELECT DISTINCT ci.id, ci.timestamp, ci.type, ci.data, ci.thumbnail, ci.name, ci.format_type, ci.formatted_content, ci.is_secret
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
                    "name": row["name"],
                    "format_type": row["format_type"],
                    "formatted_content": row["formatted_content"],
                    "is_secret": bool(row["is_secret"]),
                }
            )
        return items

    def get_file_extensions(self) -> List[str]:
        """
        Get unique file extensions from file-type clipboard items

        Returns:
            List of file extensions (e.g., ['.zip', '.sh', '.txt'])
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT DISTINCT data FROM clipboard_items
            WHERE type = 'file'
            ORDER BY id DESC
            LIMIT 100
            """
        )

        extensions = set()
        for row in cursor.fetchall():
            try:
                data = row["data"]
                # Extract metadata from file data
                separator = b"\n---FILE_CONTENT---\n"
                if separator in data:
                    metadata_bytes, _ = data.split(separator, 1)
                    metadata_json = metadata_bytes.decode("utf-8")
                    metadata = json.loads(metadata_json)
                    extension = metadata.get("extension", "")
                    if extension:
                        extensions.add(extension)
            except Exception:
                continue

        return sorted(list(extensions))

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
