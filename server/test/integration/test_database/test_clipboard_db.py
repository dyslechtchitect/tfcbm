"""Tests for ClipboardDB core operations."""

import pytest
from datetime import datetime

from database import ClipboardDB
from fixtures.database import temp_db, temp_db_file, populated_db
from fixtures.test_data import (
    generate_random_text,
    generate_random_image,
    generate_file_data,
    generate_timestamp
)


class TestClipboardDBCoreOperations:
    """Test core database operations."""

    def test_add_text_item_with_metadata(self, temp_db: ClipboardDB):
        """Test adding a text item with metadata."""
        data = b"Hello, World!"
        timestamp = generate_timestamp()

        item_id = temp_db.add_item("text", data, timestamp=timestamp)

        assert item_id is not None
        assert item_id > 0

        # Verify item was stored
        item = temp_db.get_item(item_id)
        assert item is not None
        assert item["type"] == "text"
        assert item["data"] == data
        assert item["timestamp"] == timestamp

    def test_add_image_item_with_thumbnail(self, temp_db: ClipboardDB):
        """Test adding an image item with thumbnail."""
        data = generate_random_image()
        thumbnail = generate_random_image(width=50, height=50)
        timestamp = generate_timestamp()

        item_id = temp_db.add_item(
            "image/png",
            data,
            timestamp=timestamp,
            thumbnail=thumbnail
        )

        assert item_id > 0

        item = temp_db.get_item(item_id)
        assert item["type"] == "image/png"
        assert item["data"] == data
        assert item["thumbnail"] == thumbnail

    def test_add_file_item_with_metadata(self, temp_db: ClipboardDB):
        """Test adding a file item with metadata."""
        filename = "test_document.pdf"
        data = generate_file_data(filename)
        timestamp = generate_timestamp()

        item_id = temp_db.add_item(
            "file",
            data,
            timestamp=timestamp,
            name=filename
        )

        assert item_id > 0

        item = temp_db.get_item(item_id)
        assert item["type"] == "file"
        assert item["data"] == data
        assert item["name"] == filename

    def test_get_item_by_id(self, populated_db: ClipboardDB):
        """Test retrieving a single item by ID."""
        # Add a known item
        item_id = populated_db.add_item("text", b"Test Item")

        item = populated_db.get_item(item_id)

        assert item is not None
        assert item["id"] == item_id
        assert item["data"] == b"Test Item"

    def test_get_item_nonexistent_returns_none(self, temp_db: ClipboardDB):
        """Test getting a non-existent item returns None."""
        item = temp_db.get_item(99999)
        assert item is None

    def test_get_items_with_pagination(self, populated_db: ClipboardDB):
        """Test retrieving items with pagination."""
        # Get first page
        items_page1 = populated_db.get_items(limit=3, offset=0)
        assert len(items_page1) == 3

        # Get second page
        items_page2 = populated_db.get_items(limit=3, offset=3)
        assert len(items_page2) == 3

        # Ensure pages are different
        ids_page1 = {item["id"] for item in items_page1}
        ids_page2 = {item["id"] for item in items_page2}
        assert ids_page1.isdisjoint(ids_page2)

    def test_get_total_count(self, populated_db: ClipboardDB):
        """Test getting total item count."""
        count = populated_db.get_total_count()
        assert count == 6  # 3 text + 2 images + 1 file from populated_db

    def test_get_latest_id(self, populated_db: ClipboardDB):
        """Test getting the latest item ID."""
        # Add a new item
        new_id = populated_db.add_item("text", b"Latest item")

        latest_id = populated_db.get_latest_id()
        assert latest_id == new_id

    def test_get_latest_id_empty_db(self, temp_db: ClipboardDB):
        """Test getting latest ID from empty database."""
        latest_id = temp_db.get_latest_id()
        assert latest_id is None

    def test_delete_item_by_id(self, populated_db: ClipboardDB):
        """Test deleting an item by ID."""
        item_id = populated_db.add_item("text", b"To be deleted")

        # Verify item exists
        assert populated_db.get_item(item_id) is not None

        # Delete item
        result = populated_db.delete_item(item_id)
        assert result is True

        # Verify item no longer exists
        assert populated_db.get_item(item_id) is None

    def test_delete_nonexistent_item_returns_false(self, temp_db: ClipboardDB):
        """Test deleting a non-existent item returns False."""
        result = temp_db.delete_item(99999)
        assert result is False

    def test_update_timestamp(self, temp_db: ClipboardDB):
        """Test updating an item's timestamp."""
        original_timestamp = "2025-01-01T10:00:00"
        item_id = temp_db.add_item("text", b"Test", timestamp=original_timestamp)

        new_timestamp = "2025-01-02T15:30:00"
        result = temp_db.update_timestamp(item_id, new_timestamp)

        assert result is True
        item = temp_db.get_item(item_id)
        assert item["timestamp"] == new_timestamp

    def test_update_timestamp_auto_generated(self, temp_db: ClipboardDB):
        """Test updating timestamp with auto-generated value."""
        item_id = temp_db.add_item("text", b"Test")

        result = temp_db.update_timestamp(item_id)
        assert result is True

        # Timestamp should be updated (can't assert exact value, but item should exist)
        item = temp_db.get_item(item_id)
        assert item is not None

    def test_update_thumbnail(self, temp_db: ClipboardDB):
        """Test updating an item's thumbnail."""
        item_id = temp_db.add_item("image/png", generate_random_image())

        new_thumbnail = generate_random_image(width=100, height=100)
        result = temp_db.update_thumbnail(item_id, new_thumbnail)

        assert result is True
        item = temp_db.get_item(item_id)
        assert item["thumbnail"] == new_thumbnail


class TestHashAndDeduplication:
    """Test hash calculation and deduplication."""

    def test_calculate_hash_for_text(self):
        """Test hash calculation for text data."""
        data = b"Hello, World!"
        hash1 = ClipboardDB.calculate_hash(data)
        hash2 = ClipboardDB.calculate_hash(data)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex digest

    def test_calculate_hash_for_binary_data(self):
        """Test hash calculation for binary data."""
        data = generate_random_image()
        hash1 = ClipboardDB.calculate_hash(data)

        assert hash1 is not None
        assert len(hash1) == 64

    def test_calculate_hash_large_file_uses_first_64kb(self):
        """Test that large files only hash first 64KB."""
        # Create data larger than 64KB
        large_data = b"x" * (65536 + 1000)
        small_data = b"x" * 65536

        hash_large = ClipboardDB.calculate_hash(large_data)
        hash_small = ClipboardDB.calculate_hash(small_data)

        # Hashes should be the same (first 64KB)
        assert hash_large == hash_small

    def test_get_item_by_hash_exists(self, temp_db: ClipboardDB):
        """Test getting item by hash when it exists."""
        data = b"Test data"
        data_hash = ClipboardDB.calculate_hash(data)

        item_id = temp_db.add_item("text", data, data_hash=data_hash)

        found_id = temp_db.get_item_by_hash(data_hash)
        assert found_id == item_id

    def test_get_item_by_hash_not_exists(self, temp_db: ClipboardDB):
        """Test getting item by hash when it doesn't exist."""
        fake_hash = "0" * 64
        found_id = temp_db.get_item_by_hash(fake_hash)
        assert found_id is None

    def test_hash_exists(self, temp_db: ClipboardDB):
        """Test checking if hash exists."""
        data = b"Test data"
        data_hash = ClipboardDB.calculate_hash(data)

        # Hash should not exist initially
        assert temp_db.hash_exists(data_hash) is False

        # Add item
        temp_db.add_item("text", data, data_hash=data_hash)

        # Hash should now exist
        assert temp_db.hash_exists(data_hash) is True

    def test_duplicate_detection_works_correctly(self, temp_db: ClipboardDB):
        """Test that duplicate detection identifies same content."""
        data = b"Duplicate content"

        # Add first item
        item_id1 = temp_db.add_item("text", data)
        hash1 = temp_db.get_item(item_id1)["hash"]

        # Check if hash exists before adding duplicate
        assert temp_db.hash_exists(hash1) is True

        # Get item by hash
        found_id = temp_db.get_item_by_hash(hash1)
        assert found_id == item_id1


class TestPastedItemsTracking:
    """Test pasted items tracking functionality."""

    def test_record_paste_event(self, populated_db: ClipboardDB):
        """Test recording a paste event."""
        # Get an existing item
        items = populated_db.get_items(limit=1)
        item_id = items[0]["id"]

        # Record paste
        paste_id = populated_db.add_pasted_item(item_id)

        assert paste_id > 0

    def test_get_recently_pasted_items(self, populated_db: ClipboardDB):
        """Test retrieving recently pasted items."""
        # Get some items and paste them
        items = populated_db.get_items(limit=3)
        for item in items:
            populated_db.add_pasted_item(item["id"])

        # Get recently pasted
        pasted = populated_db.get_recently_pasted(limit=10)

        assert len(pasted) == 3
        # Should be sorted by paste time (most recent first)
        assert pasted[0]["pasted_timestamp"] >= pasted[1]["pasted_timestamp"]

    def test_get_pasted_count(self, populated_db: ClipboardDB):
        """Test getting pasted item count."""
        # Paste some items
        items = populated_db.get_items(limit=3)
        for item in items:
            populated_db.add_pasted_item(item["id"])

        count = populated_db.get_pasted_count()
        assert count == 3

    def test_pasted_items_sorted_by_paste_time(self, populated_db: ClipboardDB):
        """Test that pasted items are sorted by paste timestamp."""
        items = populated_db.get_items(limit=3)

        # Paste items with specific timestamps
        paste_id1 = populated_db.add_pasted_item(items[0]["id"], "2025-01-01T10:00:00")
        paste_id2 = populated_db.add_pasted_item(items[1]["id"], "2025-01-01T11:00:00")
        paste_id3 = populated_db.add_pasted_item(items[2]["id"], "2025-01-01T12:00:00")

        # Get recently pasted (DESC order by default)
        pasted = populated_db.get_recently_pasted()

        # Most recent should be first
        assert pasted[0]["paste_id"] == paste_id3
        assert pasted[1]["paste_id"] == paste_id2
        assert pasted[2]["paste_id"] == paste_id1
