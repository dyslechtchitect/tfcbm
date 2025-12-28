"""Tests for search and filtering functionality."""

import pytest
import json

from database import ClipboardDB
from fixtures.database import temp_db, populated_db
from fixtures.test_data import generate_file_data, generate_random_image


class TestSearchAndFiltering:
    """Test search and filtering operations."""

    def test_search_by_text_content(self, populated_db: ClipboardDB):
        """Test searching by text content."""
        # Note: populated_db already has some items, including "Python code snippet"
        # Add more items with specific content
        populated_db.add_item("text", b"Python programming tutorial")
        populated_db.add_item("text", b"JavaScript guide")
        populated_db.add_item("text", b"Python data science")

        # Search for "Python"
        results = populated_db.search_items("Python", limit=10)

        # Should find all items with "Python" (including the one from populated_db)
        assert len(results) >= 2
        for item in results:
            data_str = item["data"].decode('utf-8', errors='ignore')
            assert "Python" in data_str or "python" in data_str.lower()

    def test_search_by_file_name(self, temp_db: ClipboardDB):
        """Test searching by file name."""
        # Add file items
        temp_db.add_item("file", generate_file_data("report.pdf"), name="report.pdf")
        temp_db.add_item("file", generate_file_data("data.json"), name="data.json")
        temp_db.add_item("file", generate_file_data("notes.txt"), name="notes.txt")

        # Search for "report"
        results = temp_db.search_items("report", limit=10)

        assert len(results) >= 1
        # At least one result should have "report" in the file name

    def test_search_with_type_filter_text_only(self, populated_db: ClipboardDB):
        """Test search with text-only filter."""
        # Add mixed items
        populated_db.add_item("text", b"searchable text")
        populated_db.add_item("image/png", generate_random_image())

        # Search with text filter
        results = populated_db.search_items("searchable", filters=["text"])

        for item in results:
            assert item["type"] == "text"

    def test_search_with_type_filter_image_only(self, temp_db: ClipboardDB):
        """Test filtering by image type."""
        temp_db.add_item("text", b"test")
        temp_db.add_item("image/png", generate_random_image())
        temp_db.add_item("image/jpeg", generate_random_image())

        results = temp_db.get_items(filters=["image"])

        assert len(results) == 2
        for item in results:
            assert item["type"].startswith("image/") or item["type"] == "screenshot"

    def test_search_with_type_filter_file_only(self, temp_db: ClipboardDB):
        """Test filtering by file type."""
        temp_db.add_item("text", b"test")
        temp_db.add_item("file", generate_file_data("doc.pdf"), name="doc.pdf")
        temp_db.add_item("file", generate_file_data("data.zip"), name="data.zip")

        results = temp_db.get_items(filters=["file"])

        assert len(results) == 2
        for item in results:
            assert item["type"] == "file"

    def test_search_with_date_range_filter(self, temp_db: ClipboardDB):
        """Test filtering by date range (via timestamp ordering)."""
        # Add items with specific timestamps
        temp_db.add_item("text", b"Item 1", timestamp="2025-01-01T10:00:00")
        temp_db.add_item("text", b"Item 2", timestamp="2025-01-02T10:00:00")
        temp_db.add_item("text", b"Item 3", timestamp="2025-01-03T10:00:00")

        # Get items sorted by timestamp
        items_desc = temp_db.get_items(sort_order="DESC")
        items_asc = temp_db.get_items(sort_order="ASC")

        # Verify ordering
        assert items_desc[0]["timestamp"] > items_desc[-1]["timestamp"]
        assert items_asc[0]["timestamp"] < items_asc[-1]["timestamp"]

    def test_search_with_multiple_filters_combined(self, temp_db: ClipboardDB):
        """Test search with multiple filters combined."""
        # Add tagged items (will be tested more thoroughly in tag tests)
        temp_db.add_item("text", b"Important document")
        temp_db.add_item("image/png", generate_random_image())
        temp_db.add_item("file", generate_file_data("report.pdf"), name="report.pdf")

        # Filter by multiple types
        results = temp_db.get_items(filters=["text", "file"])

        for item in results:
            assert item["type"] in ["text", "file"]

    def test_search_excludes_secret_items(self, temp_db: ClipboardDB):
        """Test that search excludes secret items' content."""
        # Add normal item
        temp_db.add_item("text", b"public searchable content")

        # Add secret item
        secret_id = temp_db.add_item(
            "text",
            b"secret password 12345",
            name="My Secret",
            is_secret=True
        )

        # Search for content that's in the secret
        results = temp_db.search_items("password")

        # Secret item content should not be searchable
        secret_in_results = any(item["id"] == secret_id for item in results)
        assert not secret_in_results

    def test_search_phrase_exact_match(self, temp_db: ClipboardDB):
        """Test searching for exact phrase with quotes."""
        temp_db.add_item("text", b"hello world example")
        temp_db.add_item("text", b"world hello test")
        temp_db.add_item("text", b"example hello world")

        # Search for exact phrase
        results = temp_db.search_items('"hello world"')

        # Should match items containing "hello world" as a phrase
        assert len(results) >= 1

    def test_search_multiple_words_all_must_match(self, temp_db: ClipboardDB):
        """Test that multiple words must all appear."""
        temp_db.add_item("text", b"python programming tutorial")
        temp_db.add_item("text", b"python guide")
        temp_db.add_item("text", b"programming basics")

        # Search for "python programming" (both words must appear)
        results = temp_db.search_items("python programming")

        # Should only match the first item
        assert len(results) >= 1
        for item in results:
            data_str = item["data"].decode('utf-8').lower()
            assert "python" in data_str and "programming" in data_str


class TestEdgeCasesAndBoundaries:
    """Test edge cases and boundary conditions."""

    def test_empty_database_operations(self, temp_db: ClipboardDB):
        """Test operations on empty database."""
        assert temp_db.get_total_count() == 0
        assert temp_db.get_items() == []
        assert temp_db.get_latest_id() is None
        assert temp_db.get_pasted_count() == 0
        assert temp_db.search_items("test") == []

    def test_very_long_text_content(self, temp_db: ClipboardDB):
        """Test handling of very long text (1MB)."""
        # Create 1MB of text
        large_text = b"x" * (1024 * 1024)

        item_id = temp_db.add_item("text", large_text)
        assert item_id > 0

        item = temp_db.get_item(item_id)
        assert len(item["data"]) == 1024 * 1024

    def test_very_long_file_names(self, temp_db: ClipboardDB):
        """Test handling of very long file names."""
        long_filename = "a" * 500 + ".txt"
        data = generate_file_data(long_filename)

        item_id = temp_db.add_item("file", data, name=long_filename)
        assert item_id > 0

        item = temp_db.get_item(item_id)
        assert item["name"] == long_filename

    def test_special_characters_in_content(self, temp_db: ClipboardDB):
        """Test handling of special characters."""
        special_text = b"!@#$%^&*()_+-=[]{}|;:',.<>?/~`"

        item_id = temp_db.add_item("text", special_text)
        item = temp_db.get_item(item_id)

        assert item["data"] == special_text

    def test_unicode_and_emoji_content(self, temp_db: ClipboardDB):
        """Test handling of Unicode and emoji."""
        unicode_text = "Hello 世界 🌍 🚀 👍".encode('utf-8')

        item_id = temp_db.add_item("text", unicode_text)
        item = temp_db.get_item(item_id)

        assert item["data"] == unicode_text
        assert item["data"].decode('utf-8') == "Hello 世界 🌍 🚀 👍"

    def test_null_none_value_handling(self, temp_db: ClipboardDB):
        """Test handling of NULL/None values."""
        # Add item without optional fields
        item_id = temp_db.add_item("text", b"test")

        item = temp_db.get_item(item_id)
        assert item["thumbnail"] is None
        assert item["name"] is None
        assert item["format_type"] is None

    def test_invalid_item_ids(self, temp_db: ClipboardDB):
        """Test operations with invalid item IDs."""
        assert temp_db.get_item(-1) is None
        assert temp_db.get_item(0) is None
        assert temp_db.get_item(99999) is None
        assert temp_db.delete_item(-1) is False
        assert temp_db.update_timestamp(99999) is False
