"""Tests for ClipboardItemRow component."""

import pytest


def test_clipboard_item_row_text():
    pytest.importorskip("gi.repository.Gtk")
    from ui.rows.clipboard_item_row import ClipboardItemRow

    item = {
        "id": 1,
        "type": "text",
        "content": "Hello World",
        "timestamp": "2024-01-01T12:00:00",
        "tags": [],
    }

    callbacks_called = []

    def on_copy():
        callbacks_called.append("copy")

    def on_view():
        callbacks_called.append("view")

    def on_save():
        callbacks_called.append("save")

    def on_tags():
        callbacks_called.append("tags")

    def on_name_save(item_id, name):
        callbacks_called.append(("name_save", item_id, name))

    row = ClipboardItemRow(
        item=item,
        on_copy=on_copy,
        on_view=on_view,
        on_save=on_save,
        on_tags=on_tags,
        on_name_save=on_name_save,
    )

    widget = row.build()

    assert widget is not None


def test_clipboard_item_row_with_search():
    pytest.importorskip("gi.repository.Gtk")
    from ui.rows.clipboard_item_row import ClipboardItemRow

    item = {
        "id": 2,
        "type": "text",
        "content": "Search me",
        "timestamp": "2024-01-01T12:00:00",
        "tags": [],
    }

    row = ClipboardItemRow(
        item=item,
        search_query="search",
        on_copy=lambda: None,
        on_view=lambda: None,
        on_save=lambda: None,
        on_tags=lambda: None,
        on_name_save=lambda item_id, name: None,
    )

    assert row.search_query == "search"


def test_clipboard_item_row_with_tags():
    pytest.importorskip("gi.repository.Gtk")
    from ui.rows.clipboard_item_row import ClipboardItemRow

    item = {
        "id": 3,
        "type": "text",
        "content": "Tagged item",
        "timestamp": "2024-01-01T12:00:00",
        "tags": [{"id": 1, "name": "work", "color": "#ff0000"}],
    }

    row = ClipboardItemRow(
        item=item,
        on_copy=lambda: None,
        on_view=lambda: None,
        on_save=lambda: None,
        on_tags=lambda: None,
        on_name_save=lambda item_id, name: None,
    )

    widget = row.build()

    assert widget is not None
