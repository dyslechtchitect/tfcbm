"""Tests for ItemActions component."""

import pytest


def test_item_actions_creation():
    pytest.importorskip("gi.repository.Gtk")
    from ui.components.items.item_actions import ItemActions

    item = {"id": 1, "type": "text", "content": "test"}
    actions = ItemActions(
        item=item,
        on_copy=lambda: None,
        on_view=lambda: None,
        on_save=lambda: None,
        on_tags=lambda: None,
        on_secret=lambda: None,
        on_delete=lambda: None,
    )

    assert actions.item == item


def test_item_actions_build_widget():
    pytest.importorskip("gi.repository.Gtk")
    from ui.components.items.item_actions import ItemActions

    item = {"id": 1, "type": "text", "content": "test"}
    actions = ItemActions(
        item=item,
        on_copy=lambda: None,
        on_view=lambda: None,
        on_save=lambda: None,
        on_tags=lambda: None,
        on_secret=lambda: None,
        on_delete=lambda: None,
    )

    widget = actions.build()

    assert widget is not None


def test_item_actions_callbacks_invoked():
    pytest.importorskip("gi.repository.Gtk")
    from ui.components.items.item_actions import ItemActions

    copy_called = False
    view_called = False
    save_called = False
    tags_called = False
    delete_called = False
    secret_called = False

    def on_copy():
        nonlocal copy_called
        copy_called = True

    def on_view():
        nonlocal view_called
        view_called = True

    def on_save():
        nonlocal save_called
        save_called = True

    def on_tags():
        nonlocal tags_called
        tags_called = True

    def on_delete():
        nonlocal delete_called
        delete_called = True

    def on_secret():
        nonlocal secret_called
        secret_called = True

    item = {"id": 1, "type": "text", "content": "test"}
    actions = ItemActions(
        item=item,
        on_copy=on_copy,
        on_view=on_view,
        on_save=on_save,
        on_tags=on_tags,
        on_secret=on_secret,
        on_delete=on_delete,
    )

    actions._trigger_copy()
    actions._trigger_view()
    actions._trigger_save()
    actions._trigger_tags()
    actions._trigger_secret()
    actions._trigger_delete()

    assert copy_called
    assert view_called
    assert save_called
    assert tags_called
    assert secret_called
    assert delete_called
