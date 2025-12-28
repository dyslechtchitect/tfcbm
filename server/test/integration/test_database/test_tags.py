"""Tests for tag management functionality."""

import pytest
import sqlite3

from database import ClipboardDB
from fixtures.database import temp_db, populated_db


class TestTagsOperations:
    """Test tag CRUD operations."""

    def test_create_tag_with_name_and_color(self, temp_db: ClipboardDB):
        """Test creating a tag with name and color."""
        tag_id = temp_db.create_tag("Important", color="#ff0000")

        assert tag_id > 0

        tag = temp_db.get_tag(tag_id)
        assert tag["name"] == "Important"
        assert tag["color"] == "#ff0000"

    def test_create_tag_with_auto_color(self, temp_db: ClipboardDB):
        """Test creating a tag with automatically assigned color."""
        tag_id = temp_db.create_tag("Work")

        tag = temp_db.get_tag(tag_id)
        assert tag["name"] == "Work"
        # Color should be from the palette
        assert tag["color"] in ClipboardDB.TAG_COLOR_PALETTE

    def test_create_tag_with_description(self, temp_db: ClipboardDB):
        """Test creating a tag with description."""
        tag_id = temp_db.create_tag(
            "Project",
            description="Work project related items",
            color="#00ff00"
        )

        tag = temp_db.get_tag(tag_id)
        assert tag["description"] == "Work project related items"

    def test_get_all_tags(self, temp_db: ClipboardDB):
        """Test retrieving all tags."""
        # Create multiple tags
        temp_db.create_tag("Tag1")
        temp_db.create_tag("Tag2")
        temp_db.create_tag("Tag3")

        tags = temp_db.get_all_tags()

        assert len(tags) == 3
        tag_names = [tag["name"] for tag in tags]
        assert "Tag1" in tag_names
        assert "Tag2" in tag_names
        assert "Tag3" in tag_names

    def test_get_tag_by_id(self, temp_db: ClipboardDB):
        """Test retrieving a single tag by ID."""
        tag_id = temp_db.create_tag("TestTag", color="#123456")

        tag = temp_db.get_tag(tag_id)

        assert tag is not None
        assert tag["id"] == tag_id
        assert tag["name"] == "TestTag"

    def test_get_tag_nonexistent_returns_none(self, temp_db: ClipboardDB):
        """Test getting a non-existent tag returns None."""
        tag = temp_db.get_tag(99999)
        assert tag is None

    def test_update_tag_properties(self, temp_db: ClipboardDB):
        """Test updating tag properties."""
        tag_id = temp_db.create_tag("OldName", color="#000000")

        # Update name and color
        temp_db.update_tag(tag_id, name="NewName", color="#ffffff")

        tag = temp_db.get_tag(tag_id)
        assert tag["name"] == "NewName"
        assert tag["color"] == "#ffffff"

    def test_update_tag_description_only(self, temp_db: ClipboardDB):
        """Test updating only the description."""
        tag_id = temp_db.create_tag("Tag", description="Old description")

        temp_db.update_tag(tag_id, description="New description")

        tag = temp_db.get_tag(tag_id)
        assert tag["description"] == "New description"
        assert tag["name"] == "Tag"  # Name unchanged

    def test_delete_tag(self, temp_db: ClipboardDB):
        """Test deleting a tag."""
        tag_id = temp_db.create_tag("ToDelete")

        result = temp_db.delete_tag(tag_id)
        assert result is True

        # Tag should no longer exist
        tag = temp_db.get_tag(tag_id)
        assert tag is None

    def test_delete_nonexistent_tag_returns_false(self, temp_db: ClipboardDB):
        """Test deleting a non-existent tag returns False."""
        result = temp_db.delete_tag(99999)
        assert result is False

    def test_create_duplicate_tag_name_raises_error(self, temp_db: ClipboardDB):
        """Test that creating a tag with duplicate name raises error."""
        temp_db.create_tag("Duplicate")

        with pytest.raises(sqlite3.IntegrityError):
            temp_db.create_tag("Duplicate")


class TestItemTagRelationships:
    """Test item-tag association operations."""

    def test_add_tag_to_item(self, populated_db: ClipboardDB):
        """Test adding a tag to an item."""
        # Create a tag
        tag_id = populated_db.create_tag("Important")

        # Get an item
        items = populated_db.get_items(limit=1)
        item_id = items[0]["id"]

        # Add tag to item
        result = populated_db.add_tag_to_item(item_id, tag_id)
        assert result is True

    def test_remove_tag_from_item(self, populated_db: ClipboardDB):
        """Test removing a tag from an item."""
        tag_id = populated_db.create_tag("ToRemove")
        items = populated_db.get_items(limit=1)
        item_id = items[0]["id"]

        # Add tag
        populated_db.add_tag_to_item(item_id, tag_id)

        # Remove tag
        result = populated_db.remove_tag_from_item(item_id, tag_id)
        assert result is True

        # Verify tag is removed
        tags = populated_db.get_tags_for_item(item_id)
        tag_ids = [tag["id"] for tag in tags]
        assert tag_id not in tag_ids

    def test_get_tags_for_item(self, populated_db: ClipboardDB):
        """Test retrieving all tags for an item."""
        # Create tags
        tag1_id = populated_db.create_tag("Tag1")
        tag2_id = populated_db.create_tag("Tag2")

        # Get an item
        items = populated_db.get_items(limit=1)
        item_id = items[0]["id"]

        # Add tags to item
        populated_db.add_tag_to_item(item_id, tag1_id)
        populated_db.add_tag_to_item(item_id, tag2_id)

        # Get tags for item
        tags = populated_db.get_tags_for_item(item_id)

        assert len(tags) == 2
        tag_ids = [tag["id"] for tag in tags]
        assert tag1_id in tag_ids
        assert tag2_id in tag_ids

    def test_get_items_by_tag_ids_any_match(self, populated_db: ClipboardDB):
        """Test getting items by tag IDs (match any)."""
        # Create tags
        tag1_id = populated_db.create_tag("Tag1")
        tag2_id = populated_db.create_tag("Tag2")

        # Add tags to items
        items = populated_db.get_items(limit=3)
        populated_db.add_tag_to_item(items[0]["id"], tag1_id)
        populated_db.add_tag_to_item(items[1]["id"], tag2_id)
        populated_db.add_tag_to_item(items[2]["id"], tag1_id)

        # Get items with either tag1 or tag2
        results = populated_db.get_items_by_tags([tag1_id, tag2_id], match_all=False)

        assert len(results) == 3

    def test_get_items_by_tag_ids_all_match(self, populated_db: ClipboardDB):
        """Test getting items by tag IDs (match all)."""
        # Create tags
        tag1_id = populated_db.create_tag("Tag1")
        tag2_id = populated_db.create_tag("Tag2")

        # Add both tags to one item, only one tag to another
        items = populated_db.get_items(limit=2)
        populated_db.add_tag_to_item(items[0]["id"], tag1_id)
        populated_db.add_tag_to_item(items[0]["id"], tag2_id)
        populated_db.add_tag_to_item(items[1]["id"], tag1_id)

        # Get items with BOTH tags
        results = populated_db.get_items_by_tags([tag1_id, tag2_id], match_all=True)

        assert len(results) == 1
        assert results[0]["id"] == items[0]["id"]

    def test_delete_tag_removes_all_associations(self, populated_db: ClipboardDB):
        """Test that deleting a tag removes all item associations."""
        tag_id = populated_db.create_tag("ToDelete")

        # Add tag to multiple items
        items = populated_db.get_items(limit=3)
        for item in items:
            populated_db.add_tag_to_item(item["id"], tag_id)

        # Delete the tag
        populated_db.delete_tag(tag_id)

        # Verify associations are removed
        for item in items:
            tags = populated_db.get_tags_for_item(item["id"])
            tag_ids = [tag["id"] for tag in tags]
            assert tag_id not in tag_ids

    def test_add_same_tag_twice_returns_false(self, populated_db: ClipboardDB):
        """Test that adding the same tag twice returns False."""
        tag_id = populated_db.create_tag("Tag")
        items = populated_db.get_items(limit=1)
        item_id = items[0]["id"]

        # Add tag first time
        result1 = populated_db.add_tag_to_item(item_id, tag_id)
        assert result1 is True

        # Add tag second time (should fail)
        result2 = populated_db.add_tag_to_item(item_id, tag_id)
        assert result2 is False

    def test_remove_nonexistent_tag_from_item_returns_false(self, populated_db: ClipboardDB):
        """Test removing a tag that's not on an item returns False."""
        tag_id = populated_db.create_tag("Tag")
        items = populated_db.get_items(limit=1)
        item_id = items[0]["id"]

        # Try to remove tag that was never added
        result = populated_db.remove_tag_from_item(item_id, tag_id)
        assert result is False


class TestTagColors:
    """Test tag color functionality."""

    def test_get_random_tag_color(self):
        """Test getting a random tag color from palette."""
        color = ClipboardDB.get_random_tag_color()

        assert color in ClipboardDB.TAG_COLOR_PALETTE

    def test_get_system_tag_color(self):
        """Test getting system tag colors for item types."""
        text_color = ClipboardDB.get_system_tag_color("text")
        image_color = ClipboardDB.get_system_tag_color("image/png")
        file_color = ClipboardDB.get_system_tag_color("file")

        assert text_color == "#3584e4"  # Blue
        assert image_color == "#33d17a"  # Green
        assert file_color == "#c061cb"  # Purple

    def test_get_system_tag_color_unknown_type_returns_default(self):
        """Test that unknown types return default gray color."""
        color = ClipboardDB.get_system_tag_color("unknown_type")
        assert color == "#9a9996"  # Gray
