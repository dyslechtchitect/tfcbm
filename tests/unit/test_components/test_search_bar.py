"""Tests for SearchBar component."""

import pytest


def test_search_bar_build():
    pytest.importorskip("gi.repository.Gtk")
    from ui.components.search_bar import SearchBar

    searches = []

    def on_search(query):
        searches.append(query)

    search_bar = SearchBar(on_search=on_search)
    widget = search_bar.build()

    assert widget is not None


def test_search_bar_with_placeholder():
    pytest.importorskip("gi.repository.Gtk")
    from ui.components.search_bar import SearchBar

    search_bar = SearchBar(
        on_search=lambda q: None, placeholder="Search items..."
    )
    widget = search_bar.build()

    assert widget is not None
    assert search_bar.placeholder == "Search items..."


def test_search_bar_default_placeholder():
    pytest.importorskip("gi.repository.Gtk")
    from ui.components.search_bar import SearchBar

    search_bar = SearchBar(on_search=lambda q: None)

    assert search_bar.placeholder == "Search clipboard items..."
