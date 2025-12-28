"""Performance tests for database operations."""

import pytest
import time

from database import ClipboardDB
from fixtures.database import temp_db
from fixtures.test_data import generate_random_text, generate_random_image


class TestDatabasePerformance:
    """Test database performance with large datasets."""

    @pytest.mark.slow
    def test_insert_10000_items_performance(self, temp_db: ClipboardDB):
        """Test inserting 10,000 items and measure performance."""
        start_time = time.time()

        # Insert 10,000 text items
        for i in range(10000):
            temp_db.add_item("text", generate_random_text(50))

        elapsed = time.time() - start_time

        # Verify all items were inserted
        count = temp_db.get_total_count()
        assert count == 10000

        # Performance assertion: should complete in reasonable time
        # (adjust threshold based on your performance requirements)
        print(f"\nInserted 10,000 items in {elapsed:.2f} seconds ({10000/elapsed:.0f} items/sec)")
        assert elapsed < 30  # Should complete within 30 seconds

    @pytest.mark.slow
    def test_search_across_10000_items(self, temp_db: ClipboardDB):
        """Test search performance with 10,000 items."""
        # Insert 10,000 items, some with search term
        for i in range(10000):
            if i % 100 == 0:
                temp_db.add_item("text", b"Python special keyword item")
            else:
                temp_db.add_item("text", generate_random_text(50))

        # Search for the keyword
        start_time = time.time()
        results = temp_db.search_items("Python")
        elapsed = time.time() - start_time

        # Should find approximately 100 items
        assert len(results) >= 90  # Allow some margin

        print(f"\nSearched 10,000 items in {elapsed:.4f} seconds")
        assert elapsed < 1.0  # Should be fast with FTS index

    @pytest.mark.slow
    def test_pagination_with_large_dataset(self, temp_db: ClipboardDB):
        """Test pagination performance with large dataset."""
        # Insert 10,000 items
        for i in range(10000):
            temp_db.add_item("text", generate_random_text(20), timestamp=f"2025-01-{i//400 + 1:02d}T10:00:00")

        # Test paginated retrieval
        start_time = time.time()
        page1 = temp_db.get_items(limit=100, offset=0)
        page50 = temp_db.get_items(limit=100, offset=4900)
        page100 = temp_db.get_items(limit=100, offset=9900)
        elapsed = time.time() - start_time

        # Verify pagination works
        assert len(page1) == 100
        assert len(page50) == 100
        assert len(page100) == 100

        # IDs should be different across pages
        assert page1[0]["id"] != page50[0]["id"]
        assert page50[0]["id"] != page100[0]["id"]

        print(f"\nRetrieved 3 pages from 10,000 items in {elapsed:.4f} seconds")
        assert elapsed < 0.5  # Should be fast with proper indexing

    @pytest.mark.slow
    def test_bulk_delete_5000_items(self, temp_db: ClipboardDB):
        """Test bulk deletion performance."""
        # Insert 10,000 items
        for i in range(10000):
            temp_db.add_item("text", generate_random_text(30))

        # Delete oldest 5,000
        start_time = time.time()
        deleted = temp_db.bulk_delete_oldest(5000)
        elapsed = time.time() - start_time

        assert deleted == 5000
        assert temp_db.get_total_count() == 5000

        print(f"\nDeleted 5,000 items in {elapsed:.4f} seconds")
        assert elapsed < 5.0  # Should complete quickly

    def test_concurrent_read_performance(self, temp_db: ClipboardDB):
        """Test concurrent read operations (simulated)."""
        # Add some data
        for i in range(1000):
            temp_db.add_item("text", generate_random_text(50))

        # Simulate multiple read operations
        start_time = time.time()
        for _ in range(100):
            items = temp_db.get_items(limit=10)
            count = temp_db.get_total_count()
            latest_id = temp_db.get_latest_id()
        elapsed = time.time() - start_time

        print(f"\nCompleted 300 concurrent-style read operations in {elapsed:.4f} seconds")
        assert elapsed < 1.0  # Should be very fast for reads
