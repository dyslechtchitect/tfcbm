"""Tests for ClipboardItemRow component."""

import pytest


def test_clipboard_item_row_text():
    pytest.importorskip("gi.repository.Gtk")
    from ui.rows.clipboard_item_row import ClipboardItemRow

    # Mock window object
    class MockWindow:
        class MockSettings:
            item_height = 150

        settings = MockSettings()

        def show_notification(self, msg):
            pass

    item = {
        "id": 1,
        "type": "text",
        "content": "Hello World",
        "timestamp": "2024-01-01T12:00:00",
        "tags": [],
    }

    window = MockWindow()
    row = ClipboardItemRow(item=item, window=window, search_query="")

    assert row is not None
    assert row.item == item


def test_clipboard_item_row_with_search():
    pytest.importorskip("gi.repository.Gtk")
    from ui.rows.clipboard_item_row import ClipboardItemRow

    class MockWindow:
        class MockSettings:
            item_height = 150

        settings = MockSettings()

        def show_notification(self, msg):
            pass

    item = {
        "id": 2,
        "type": "text",
        "content": "Search me",
        "timestamp": "2024-01-01T12:00:00",
        "tags": [],
    }

    window = MockWindow()
    row = ClipboardItemRow(item=item, window=window, search_query="search")

    assert row.search_query == "search"


def test_clipboard_item_row_with_tags():
    pytest.importorskip("gi.repository.Gtk")
    from ui.rows.clipboard_item_row import ClipboardItemRow

    class MockWindow:
        class MockSettings:
            item_height = 150

        settings = MockSettings()

        def show_notification(self, msg):
            pass

    item = {
        "id": 3,
        "type": "text",
        "content": "Tagged item",
        "timestamp": "2024-01-01T12:00:00",
        "tags": [{"id": 1, "name": "work", "color": "#ff0000"}],
    }

    window = MockWindow()
    row = ClipboardItemRow(item=item, window=window)

    assert row is not None
    assert len(row.item["tags"]) == 1
