"""Tests for ItemTags component."""

import pytest


def test_item_tags_build():
    pytest.importorskip("gi.repository.Gtk")
    from ui.components.items.item_tags import ItemTags

    tags = [
        {"id": 1, "name": "work", "color": "#ff0000"},
        {"id": 2, "name": "personal", "color": "#00ff00"},
    ]
    clicked = []

    def on_click():
        clicked.append(True)

    item_tags = ItemTags(tags=tags, on_click=on_click)
    widget = item_tags.build()

    assert widget is not None


def test_item_tags_filters_system_tags():
    pytest.importorskip("gi.repository.Gtk")
    from ui.components.items.item_tags import ItemTags

    tags = [
        {"id": 1, "name": "work", "color": "#ff0000"},
        {"id": 2, "name": "system", "color": "#00ff00", "is_system": True},
    ]

    item_tags = ItemTags(tags=tags, on_click=lambda: None)

    assert len(item_tags.user_tags) == 1
    assert item_tags.user_tags[0]["name"] == "work"


def test_item_tags_empty():
    pytest.importorskip("gi.repository.Gtk")
    from ui.components.items.item_tags import ItemTags

    item_tags = ItemTags(tags=[], on_click=lambda: None)
    widget = item_tags.build()

    assert widget is not None
    assert len(item_tags.user_tags) == 0


def test_item_tags_no_callback():
    pytest.importorskip("gi.repository.Gtk")
    from ui.components.items.item_tags import ItemTags

    tags = [{"id": 1, "name": "work", "color": "#ff0000"}]
    item_tags = ItemTags(tags=tags)
    widget = item_tags.build()

    assert widget is not None
