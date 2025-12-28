"""Tests for orphaned recently_pasted records bug.

This test reproduces the issue where:
1. User pastes some clipboard items (creates recently_pasted records)
2. User reduces max_items setting (deletes old clipboard_items)
3. recently_pasted records are orphaned (reference deleted items)
4. UI shows incorrect count: "2 out of 647 items"
"""

import pytest
import sqlite3

from database import ClipboardDB
from fixtures.database import temp_db, temp_db_file
from fixtures.test_data import generate_random_text, generate_timestamp


class TestOrphanedPastedRecords:
    """Test orphaned recently_pasted records cleanup."""

    def test_bulk_delete_should_cleanup_orphaned_pasted_records(self, temp_db: ClipboardDB):
        """Test that bulk deleting items also cleans up orphaned pasted records.

        This reproduces the bug where:
        - Adding many items and pasting them
        - Bulk deleting old items (via max_items reduction)
        - Leaves orphaned recently_pasted records
        """
        # Arrange: Add 100 items
        item_ids = []
        for i in range(100):
            data = f"Item {i}".encode()
            timestamp = generate_timestamp(hours_ago=i)
            item_id = temp_db.add_item("text", data, timestamp=timestamp)
            item_ids.append(item_id)

        # Paste the first 50 items (create recently_pasted records)
        for item_id in item_ids[:50]:
            temp_db.add_pasted_item(item_id)

        # Verify initial state
        total_items = temp_db.get_total_count()
        pasted_count = temp_db.get_pasted_count()
        assert total_items == 100
        assert pasted_count == 50

        # Act: Bulk delete oldest 80 items (simulating max_items reduction)
        # This should delete items 20-99 (the 80 oldest)
        temp_db.bulk_delete_oldest(80)

        # Assert: Check counts
        remaining_items = temp_db.get_total_count()
        remaining_pasted = temp_db.get_pasted_count()

        assert remaining_items == 20, f"Should have 20 items left, got {remaining_items}"

        # The bug: remaining_pasted is still 50, but should be 20
        # because 30 of the pasted items were deleted
        # This is the FAILING assertion that proves the bug exists
        assert remaining_pasted == 20, (
            f"BUG DETECTED: Should have 20 pasted records (matching remaining items), "
            f"but got {remaining_pasted}. This means there are {remaining_pasted - 20} orphaned records."
        )

        # Verify no orphaned records exist by checking the database directly
        # The cleanup should have been called automatically
        assert remaining_pasted <= 20, (
            f"Pasted count ({remaining_pasted}) should not exceed item count ({remaining_items})"
        )

    def test_cleanup_old_items_should_cleanup_orphaned_pasted_records(self, temp_db: ClipboardDB):
        """Test that automatic cleanup (retention policy) also cleans up pasted records.

        This tests the automatic cleanup when max_items is reached.
        """
        # Arrange: Add items and paste them
        item_ids = []
        for i in range(50):
            data = f"Item {i}".encode()
            timestamp = generate_timestamp(hours_ago=i)
            item_id = temp_db.add_item("text", data, timestamp=timestamp)
            item_ids.append(item_id)

            # Paste every other item
            if i % 2 == 0:
                temp_db.add_pasted_item(item_id)

        initial_items = temp_db.get_total_count()
        initial_pasted = temp_db.get_pasted_count()
        assert initial_items == 50
        assert initial_pasted == 25  # Pasted every other item

        # Act: Trigger cleanup_old_items to keep only 20 items
        # This deletes the 30 oldest items
        temp_db.cleanup_old_items(max_items=20)

        # Assert
        remaining_items = temp_db.get_total_count()
        remaining_pasted = temp_db.get_pasted_count()

        assert remaining_items == 20

        # The pasted count should be <= 20 (only items that still exist)
        assert remaining_pasted <= 20, (
            f"Pasted count ({remaining_pasted}) should not exceed item count ({remaining_items})"
        )
