"""Tests for favorites feature."""

import pytest

from database import ClipboardDB
from fixtures.database import temp_db
from fixtures.test_data import generate_random_text, generate_timestamp


class TestFavoritesBasicOperations:
    """Test basic favorite operations."""

    def test_add_item_as_favorite(self, temp_db: ClipboardDB):
        """Test adding an item marked as favorite."""
        item_id = temp_db.add_item(
            "text",
            b"Favorite Item",
            is_favorite=True
        )

        item = temp_db.get_item(item_id)
        assert item is not None
        assert item["is_favorite"] is True

    def test_add_item_not_favorite_by_default(self, temp_db: ClipboardDB):
        """Test that items are not favorited by default."""
        item_id = temp_db.add_item("text", b"Normal Item")

        item = temp_db.get_item(item_id)
        assert item is not None
        assert item["is_favorite"] is False

    def test_toggle_favorite_on(self, temp_db: ClipboardDB):
        """Test toggling favorite status from false to true."""
        item_id = temp_db.add_item("text", b"Item to favorite")

        # Toggle favorite on
        result = temp_db.toggle_favorite(item_id, True)
        assert result is True

        # Verify it's now favorited
        item = temp_db.get_item(item_id)
        assert item["is_favorite"] is True

    def test_toggle_favorite_off(self, temp_db: ClipboardDB):
        """Test toggling favorite status from true to false."""
        item_id = temp_db.add_item("text", b"Favorite Item", is_favorite=True)

        # Toggle favorite off
        result = temp_db.toggle_favorite(item_id, False)
        assert result is True

        # Verify it's no longer favorited
        item = temp_db.get_item(item_id)
        assert item["is_favorite"] is False

    def test_toggle_favorite_nonexistent_item(self, temp_db: ClipboardDB):
        """Test toggling favorite on non-existent item."""
        result = temp_db.toggle_favorite(99999, True)
        assert result is False


class TestFavoritesFiltering:
    """Test filtering by favorite status."""

    def test_filter_favorite_items(self, temp_db: ClipboardDB):
        """Test filtering to show only favorite items."""
        # Add mix of favorite and non-favorite items
        fav1_id = temp_db.add_item("text", b"Favorite 1", is_favorite=True)
        temp_db.add_item("text", b"Normal 1", is_favorite=False)
        fav2_id = temp_db.add_item("text", b"Favorite 2", is_favorite=True)
        temp_db.add_item("text", b"Normal 2", is_favorite=False)

        # Filter for favorites
        favorites = temp_db.get_items(filters=["favorite"])

        assert len(favorites) == 2
        favorite_ids = [item["id"] for item in favorites]
        assert fav1_id in favorite_ids
        assert fav2_id in favorite_ids

    def test_filter_favorite_returns_empty_when_none(self, temp_db: ClipboardDB):
        """Test that favorite filter returns empty list when no favorites."""
        temp_db.add_item("text", b"Normal 1")
        temp_db.add_item("text", b"Normal 2")

        favorites = temp_db.get_items(filters=["favorite"])
        assert len(favorites) == 0

    def test_get_items_includes_is_favorite_field(self, temp_db: ClipboardDB):
        """Test that get_items returns is_favorite field."""
        temp_db.add_item("text", b"Favorite", is_favorite=True)
        temp_db.add_item("text", b"Normal", is_favorite=False)

        items = temp_db.get_items()

        assert len(items) == 2
        for item in items:
            assert "is_favorite" in item
            assert isinstance(item["is_favorite"], bool)


class TestFavoritesRetention:
    """Test that favorites are protected from auto-deletion."""

    def test_cleanup_excludes_favorites(self, temp_db: ClipboardDB):
        """Test that cleanup does not delete favorite items."""
        # Add 10 items: 5 favorites and 5 normal
        for i in range(5):
            temp_db.add_item(
                "text",
                f"Favorite {i}".encode(),
                timestamp=generate_timestamp(days_ago=10-i),
                is_favorite=True
            )
        for i in range(5):
            temp_db.add_item(
                "text",
                f"Normal {i}".encode(),
                timestamp=generate_timestamp(days_ago=5-i),
                is_favorite=False
            )

        # Total: 10 items (5 favorites + 5 normal)
        assert temp_db.get_total_count() == 10

        # Cleanup to keep only 3 non-favorite items
        deleted_ids = temp_db.cleanup_old_items(max_items=3)

        # Should delete 2 non-favorite items (5 - 3 = 2)
        assert len(deleted_ids) == 2

        # Should have 8 items total (5 favorites + 3 normal)
        assert temp_db.get_total_count() == 8

        # All favorites should still exist
        favorites = temp_db.get_items(filters=["favorite"])
        assert len(favorites) == 5

    def test_cleanup_only_counts_non_favorites(self, temp_db: ClipboardDB):
        """Test that cleanup only counts non-favorite items toward limit."""
        # Add 3 favorites
        for i in range(3):
            temp_db.add_item(
                "text",
                f"Favorite {i}".encode(),
                is_favorite=True
            )
        # Add 2 normal items
        for i in range(2):
            temp_db.add_item(
                "text",
                f"Normal {i}".encode(),
                is_favorite=False
            )

        # Cleanup to keep 5 non-favorite items (we only have 2)
        deleted_ids = temp_db.cleanup_old_items(max_items=5)

        # Nothing should be deleted
        assert deleted_ids == []
        assert temp_db.get_total_count() == 5

    def test_bulk_delete_oldest_excludes_favorites(self, temp_db: ClipboardDB):
        """Test that bulk_delete_oldest excludes favorite items."""
        # Add items with varying ages
        fav_id = temp_db.add_item(
            "text",
            b"Old Favorite",
            timestamp="2025-01-01T10:00:00",
            is_favorite=True
        )
        normal_id1 = temp_db.add_item(
            "text",
            b"Old Normal",
            timestamp="2025-01-02T10:00:00",
            is_favorite=False
        )
        normal_id2 = temp_db.add_item(
            "text",
            b"Recent Normal",
            timestamp="2025-01-03T10:00:00",
            is_favorite=False
        )

        # Delete oldest 2 items
        deleted = temp_db.bulk_delete_oldest(2)

        assert deleted == 2

        # Old favorite should still exist
        assert temp_db.get_item(fav_id) is not None

        # Both normal items should be deleted
        assert temp_db.get_item(normal_id1) is None
        assert temp_db.get_item(normal_id2) is None

    def test_favorites_can_be_manually_deleted(self, temp_db: ClipboardDB):
        """Test that favorite items can still be deleted manually."""
        fav_id = temp_db.add_item("text", b"Favorite", is_favorite=True)

        # Manually delete the favorite
        result = temp_db.delete_item(fav_id)

        assert result is True
        assert temp_db.get_item(fav_id) is None

    def test_cleanup_with_only_favorites(self, temp_db: ClipboardDB):
        """Test cleanup when all items are favorites."""
        # Add only favorites
        for i in range(10):
            temp_db.add_item(
                "text",
                f"Favorite {i}".encode(),
                is_favorite=True
            )

        # Try to cleanup to 5 items
        deleted_ids = temp_db.cleanup_old_items(max_items=5)

        # Nothing should be deleted (all are favorites)
        assert deleted_ids == []
        assert temp_db.get_total_count() == 10


class TestFavoritesInSearch:
    """Test favorites in search and filter operations."""

    def test_search_includes_is_favorite_field(self, temp_db: ClipboardDB):
        """Test that search results include is_favorite field."""
        temp_db.add_item("text", b"Hello world", is_favorite=True)
        temp_db.add_item("text", b"Hello universe", is_favorite=False)

        results = temp_db.search_items("hello")

        assert len(results) == 2
        for result in results:
            assert "is_favorite" in result
            assert isinstance(result["is_favorite"], bool)

    def test_search_with_favorite_filter(self, temp_db: ClipboardDB):
        """Test searching with favorite filter."""
        temp_db.add_item("text", b"Important document", is_favorite=True)
        temp_db.add_item("text", b"Normal document", is_favorite=False)
        temp_db.add_item("text", b"Important email", is_favorite=True)

        # Search for "important" with favorite filter
        results = temp_db.search_items("important", filters=["favorite"])

        assert len(results) == 2
        for result in results:
            assert result["is_favorite"] is True
            assert b"Important" in result["data"]

    def test_get_recently_pasted_includes_is_favorite(self, temp_db: ClipboardDB):
        """Test that get_recently_pasted includes is_favorite field."""
        # Add item and paste it
        item_id = temp_db.add_item("text", b"Pasted item", is_favorite=True)
        temp_db.add_pasted_item(item_id)

        # Get recently pasted items
        pasted = temp_db.get_recently_pasted(limit=10)

        assert len(pasted) == 1
        assert pasted[0]["is_favorite"] is True

    def test_get_recently_pasted_with_favorite_filter(self, temp_db: ClipboardDB):
        """Test filtering recently pasted items by favorite status."""
        # Add and paste favorite item
        fav_id = temp_db.add_item("text", b"Favorite pasted", is_favorite=True)
        temp_db.add_pasted_item(fav_id)

        # Add and paste normal item
        normal_id = temp_db.add_item("text", b"Normal pasted", is_favorite=False)
        temp_db.add_pasted_item(normal_id)

        # Filter for favorite pasted items
        pasted = temp_db.get_recently_pasted(limit=10, filters=["favorite"])

        assert len(pasted) == 1
        assert pasted[0]["is_favorite"] is True
        assert pasted[0]["id"] == fav_id

    def test_get_items_by_tags_includes_is_favorite(self, temp_db: ClipboardDB):
        """Test that get_items_by_tags includes is_favorite field."""
        # Create a tag
        tag_id = temp_db.create_tag("work")

        # Add items with tag
        item1_id = temp_db.add_item("text", b"Work item 1", is_favorite=True)
        item2_id = temp_db.add_item("text", b"Work item 2", is_favorite=False)

        # Tag the items
        temp_db.add_tag_to_item(item1_id, tag_id)
        temp_db.add_tag_to_item(item2_id, tag_id)

        # Get items by tag
        items = temp_db.get_items_by_tags([tag_id])

        assert len(items) == 2
        for item in items:
            assert "is_favorite" in item
            assert isinstance(item["is_favorite"], bool)


class TestFavoritesCombinedFilters:
    """Test favorites combined with other filters."""

    def test_favorite_with_type_filter(self, temp_db: ClipboardDB):
        """Test combining favorite filter with type filters (OR logic)."""
        # Add various items
        fav_text_id = temp_db.add_item("text", b"Favorite text", is_favorite=True)
        normal_text_id = temp_db.add_item("text", b"Normal text", is_favorite=False)
        fav_image_id = temp_db.add_item("image/png", b"png_data", is_favorite=True)
        fav_url_id = temp_db.add_item("url", b"https://example.com", is_favorite=True)

        # Get items that are favorite OR text (OR logic)
        items = temp_db.get_items(filters=["favorite", "text"])

        # Should get 4 items: all favorites (3) + normal text (1)
        assert len(items) == 4
        item_ids = [item["id"] for item in items]
        assert fav_text_id in item_ids
        assert normal_text_id in item_ids
        assert fav_image_id in item_ids
        assert fav_url_id in item_ids

    def test_favorite_with_multiple_type_filters(self, temp_db: ClipboardDB):
        """Test favorite with multiple type filters (OR logic)."""
        # Add various items
        fav_text_id = temp_db.add_item("text", b"Favorite text", is_favorite=True)
        normal_url_id = temp_db.add_item("url", b"http://normal.com", is_favorite=False)
        fav_url_id = temp_db.add_item("url", b"http://favorite.com", is_favorite=True)
        fav_image_id = temp_db.add_item("image/png", b"png_data", is_favorite=True)

        # Get items that are favorite OR text OR url (OR logic)
        items = temp_db.get_items(filters=["favorite", "text", "url"])

        # Should get all 4 items (all favorites + normal url)
        assert len(items) == 4
        item_ids = [item["id"] for item in items]
        assert fav_text_id in item_ids
        assert normal_url_id in item_ids
        assert fav_url_id in item_ids
        assert fav_image_id in item_ids
