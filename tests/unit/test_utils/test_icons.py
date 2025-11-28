"""Tests for icon utilities."""

import pytest


def test_get_file_icon_directory():
    pytest.importorskip("gi.repository.Gtk")
    from ui.utils.icons import get_file_icon

    icon = get_file_icon("myfolder", "inode/directory", True)

    assert icon == "folder"


def test_get_file_icon_text_file():
    pytest.importorskip("gi.repository.Gtk")
    from ui.utils.icons import get_file_icon

    icon = get_file_icon("test.txt", "text/plain", False)

    assert icon is not None
    assert isinstance(icon, str)


def test_get_file_icon_pdf():
    pytest.importorskip("gi.repository.Gtk")
    from ui.utils.icons import get_file_icon

    icon = get_file_icon("doc.pdf", "application/pdf", False)

    assert icon is not None
    assert isinstance(icon, str)


def test_get_file_icon_unknown():
    pytest.importorskip("gi.repository.Gtk")
    from ui.utils.icons import get_file_icon

    icon = get_file_icon("unknown", "application/octet-stream", False)

    assert icon is not None
    assert isinstance(icon, str)
