"""Tests for ItemHeader component."""

import pytest


def test_item_header_creation():
    pytest.importorskip("gi.repository.Gtk")
    from ui.components.items.item_header import ItemHeader

    item = {
        "id": 1,
        "timestamp": "2024-01-01T12:00:00",
        "name": "Test Item",
    }

    header = ItemHeader(
        item=item, on_name_save=lambda item_id, name: None, search_query=""
    )

    assert header.item == item
    assert header.search_query == ""


def test_item_header_with_pasted_timestamp():
    pytest.importorskip("gi.repository.Gtk")
    from ui.components.items.item_header import ItemHeader

    item = {
        "id": 1,
        "timestamp": "2024-01-01T12:00:00",
        "pasted_timestamp": "2024-01-01T13:00:00",
        "name": None,
    }

    header = ItemHeader(
        item=item,
        on_name_save=lambda item_id, name: None,
        show_pasted_time=True,
        search_query="",
    )

    assert header.show_pasted_time is True


def test_item_header_with_search_query():
    pytest.importorskip("gi.repository.Gtk")
    from ui.components.items.item_header import ItemHeader

    item = {"id": 1, "timestamp": "2024-01-01T12:00:00", "name": "Test"}

    header = ItemHeader(
        item=item,
        on_name_save=lambda item_id, name: None,
        search_query="test",
    )

    assert header.search_query == "test"


def test_item_header_name_save_callback():
    pytest.importorskip("gi.repository.Gtk")
    from ui.components.items.item_header import ItemHeader

    saved_name = None
    saved_id = None

    def save_callback(item_id, name):
        nonlocal saved_name, saved_id
        saved_id = item_id
        saved_name = name

    item = {"id": 42, "timestamp": "2024-01-01T12:00:00", "name": "Old"}

    header = ItemHeader(item=item, on_name_save=save_callback, search_query="")

    header._save_name("New Name")

    assert saved_id == 42
    assert saved_name == "New Name"


def test_item_header_handles_none_name():
    pytest.importorskip("gi.repository.Gtk")
    from ui.components.items.item_header import ItemHeader

    item = {"id": 1, "timestamp": "2024-01-01T12:00:00", "name": None}

    header = ItemHeader(
        item=item, on_name_save=lambda item_id, name: None, search_query=""
    )

    widget = header.build()

    assert widget is not None
