"""Tests for ItemContent component."""

import pytest


def test_item_content_text():
    pytest.importorskip("gi.repository.Gtk")
    from ui.components.items.item_content import ItemContent

    item = {"id": 1, "type": "text", "content": "Hello World"}
    content = ItemContent(item=item, search_query="")

    widget = content.build()

    assert widget is not None
    assert content.item_type == "text"


def test_item_content_text_with_search():
    pytest.importorskip("gi.repository.Gtk")
    from ui.components.items.item_content import ItemContent

    item = {"id": 1, "type": "text", "content": "Hello World"}
    content = ItemContent(item=item, search_query="world")

    assert content.search_query == "world"


def test_item_content_image():
    pytest.importorskip("gi.repository.Gtk")
    from ui.components.items.item_content import ItemContent

    item = {"id": 1, "type": "image", "content": b"fake_image_data"}
    content = ItemContent(item=item, search_query="")

    widget = content.build()

    assert widget is not None
    assert content.item_type == "image"


def test_item_content_file():
    pytest.importorskip("gi.repository.Gtk")
    from ui.components.items.item_content import ItemContent

    item = {
        "id": 1,
        "type": "file",
        "content": {
            "name": "document.pdf",
            "size": 1024,
            "mime_type": "application/pdf",
            "extension": ".pdf",
            "is_directory": False,
        },
    }
    content = ItemContent(item=item, search_query="")

    widget = content.build()

    assert widget is not None
    assert content.item_type == "file"


def test_item_content_directory():
    pytest.importorskip("gi.repository.Gtk")
    from ui.components.items.item_content import ItemContent

    item = {
        "id": 1,
        "type": "file",
        "content": {
            "name": "MyFolder",
            "size": 0,
            "mime_type": "inode/directory",
            "extension": "",
            "is_directory": True,
        },
    }
    content = ItemContent(item=item, search_query="")

    widget = content.build()

    assert widget is not None


def test_item_content_unknown_type():
    pytest.importorskip("gi.repository.Gtk")
    from ui.components.items.item_content import ItemContent

    item = {"id": 1, "type": "unknown", "content": "data"}
    content = ItemContent(item=item, search_query="")

    widget = content.build()

    assert widget is not None
