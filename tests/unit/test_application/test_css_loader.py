"""Tests for CSS loader."""

from pathlib import Path

import pytest


def test_css_loader_with_valid_file(tmp_path: Path):
    pytest.importorskip("gi.repository.Gtk")
    from ui.application.css_loader import CssLoader

    css_file = tmp_path / "test.css"
    css_file.write_text("button { color: red; }")

    loader = CssLoader()
    result = loader.load(str(css_file))

    assert result is True


def test_css_loader_with_missing_file():
    pytest.importorskip("gi.repository.Gtk")
    from ui.application.css_loader import CssLoader

    loader = CssLoader()
    result = loader.load("/nonexistent/file.css")

    assert result is False


def test_css_loader_with_invalid_path():
    pytest.importorskip("gi.repository.Gtk")
    from ui.application.css_loader import CssLoader

    loader = CssLoader()
    result = loader.load("")

    assert result is False
