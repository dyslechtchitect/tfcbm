"""Tests for retention policy and cleanup operations."""

import json
import pytest

from database import ClipboardDB
from fixtures.database import temp_db
from fixtures.test_data import generate_random_text, generate_timestamp


class TestRetentionAndCleanup:
    """Test retention policy enforcement."""

    def test_cleanup_old_items_exceeds_limit(self, temp_db: ClipboardDB):
        """Test cleanup when item count exceeds limit."""
        # Add 10 items
        for i in range(10):
            temp_db.add_item("text", generate_random_text(), timestamp=generate_timestamp(days_ago=i))

        # Cleanup to keep only 5
        deleted_ids = temp_db.cleanup_old_items(max_items=5)

        assert len(deleted_ids) == 5
        assert temp_db.get_total_count() == 5

    def test_cleanup_deletes_oldest_by_timestamp(self, temp_db: ClipboardDB):
        """Test that cleanup deletes oldest items first."""
        # Add items with specific timestamps
        id1 = temp_db.add_item("text", b"Oldest", timestamp="2025-01-01T10:00:00")
        id2 = temp_db.add_item("text", b"Middle", timestamp="2025-01-02T10:00:00")
        id3 = temp_db.add_item("text", b"Newest", timestamp="2025-01-03T10:00:00")

        # Cleanup to keep only 1
        temp_db.cleanup_old_items(max_items=1)

        # Only the newest should remain
        assert temp_db.get_item(id1) is None
        assert temp_db.get_item(id2) is None
        assert temp_db.get_item(id3) is not None

    def test_no_cleanup_when_under_limit(self, temp_db: ClipboardDB):
        """Test that no cleanup happens when under limit."""
        # Add 3 items
        for i in range(3):
            temp_db.add_item("text", generate_random_text())

        # Cleanup with limit of 10 (no cleanup needed)
        deleted_ids = temp_db.cleanup_old_items(max_items=10)

        assert deleted_ids == []
        assert temp_db.get_total_count() == 3

    def test_bulk_delete_oldest_n_items(self, temp_db: ClipboardDB):
        """Test bulk delete of specific number of oldest items."""
        # Add 10 items
        for i in range(10):
            temp_db.add_item("text", generate_random_text(), timestamp=generate_timestamp(days_ago=10-i))

        # Delete oldest 3
        deleted = temp_db.bulk_delete_oldest(3)

        assert deleted == 3
        assert temp_db.get_total_count() == 7

    def test_bulk_delete_zero_items(self, temp_db: ClipboardDB):
        """Test bulk delete with count=0."""
        temp_db.add_item("text", b"test")

        deleted = temp_db.bulk_delete_oldest(0)

        assert deleted == 0
        assert temp_db.get_total_count() == 1

    def test_bulk_delete_negative_count(self, temp_db: ClipboardDB):
        """Test bulk delete with negative count."""
        temp_db.add_item("text", b"test")

        deleted = temp_db.bulk_delete_oldest(-5)

        assert deleted == 0
        assert temp_db.get_total_count() == 1

    def test_file_extensions_extraction(self, temp_db: ClipboardDB):
        """Test extracting file extensions from file items."""
        # Add file items with different extensions
        extensions = [".pdf", ".zip", ".txt", ".jpg", ".docx"]
        for ext in extensions:
            metadata = json.dumps({"name": f"file{ext}", "extension": ext, "size": 100})
            data = metadata.encode() + b"\n---FILE_CONTENT---\n" + b"content"
            temp_db.add_item("file", data, name=f"file{ext}")

        extracted_exts = temp_db.get_file_extensions()

        # All extensions should be extracted
        for ext in extensions:
            assert ext in extracted_exts

    def test_cleanup_preserves_newest_items(self, temp_db: ClipboardDB):
        """Test that cleanup preserves the newest items."""
        # Add items with known content
        oldest_id = temp_db.add_item("text", b"oldest", timestamp="2025-01-01T00:00:00")
        middle_id = temp_db.add_item("text", b"middle", timestamp="2025-01-01T12:00:00")
        newest_id = temp_db.add_item("text", b"newest", timestamp="2025-01-02T00:00:00")

        # Keep only 2 items
        temp_db.cleanup_old_items(max_items=2)

        # Oldest should be deleted, middle and newest preserved
        assert temp_db.get_item(oldest_id) is None
        assert temp_db.get_item(middle_id) is not None
        assert temp_db.get_item(newest_id) is not None

    def test_update_item_name(self, temp_db: ClipboardDB):
        """Test updating item name."""
        item_id = temp_db.add_item("text", b"content", name="Old Name")

        result = temp_db.update_item_name(item_id, "New Name")

        assert result is True
        item = temp_db.get_item(item_id)
        assert item["name"] == "New Name"

    def test_update_item_name_to_none(self, temp_db: ClipboardDB):
        """Test clearing item name by setting to None."""
        item_id = temp_db.add_item("text", b"content", name="Some Name")

        result = temp_db.update_item_name(item_id, None)

        assert result is True
        item = temp_db.get_item(item_id)
        assert item["name"] is None
