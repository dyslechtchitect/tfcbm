"""Tests for settings configuration."""

from pathlib import Path

import pytest


def test_display_settings_defaults():
    from ui.config.settings import DisplaySettings

    settings = DisplaySettings()

    assert settings.item_width == 300
    assert settings.item_height == 150
    assert settings.max_page_length == 50


def test_display_settings_immutable():
    from ui.config.settings import DisplaySettings

    settings = DisplaySettings()

    with pytest.raises(AttributeError):
        settings.item_width = 500


def test_window_settings_defaults():
    from ui.config.settings import WindowSettings

    settings = WindowSettings()

    assert settings.default_width == 350
    assert settings.default_height == 800
    assert settings.position == "left"


def test_window_settings_custom():
    from ui.config.settings import WindowSettings

    settings = WindowSettings(
        default_width=400, default_height=600, position="right"
    )

    assert settings.default_width == 400
    assert settings.default_height == 600
    assert settings.position == "right"


def test_app_settings_composition():
    from ui.config.settings import AppSettings, DisplaySettings, WindowSettings

    display = DisplaySettings(item_width=200)
    window = WindowSettings(default_width=400)
    settings = AppSettings(display=display, window=window)

    assert settings.display.item_width == 200
    assert settings.window.default_width == 400


def test_app_settings_load_defaults():
    from ui.config.settings import AppSettings

    settings = AppSettings.load()

    assert settings.display is not None
    assert settings.window is not None


def test_app_settings_load_from_file(tmp_path: Path):
    from ui.config.settings import AppSettings

    config_file = tmp_path / "settings.yml"
    config_file.write_text(
        """
item_width: 250
item_height: 200
max_page_length: 30
"""
    )

    settings = AppSettings.load(str(config_file))

    assert settings.display.item_width == 250
    assert settings.display.item_height == 200
    assert settings.display.max_page_length == 30


def test_app_settings_load_missing_file():
    from ui.config.settings import AppSettings

    settings = AppSettings.load("/nonexistent/path.yml")

    assert settings.display is not None
    assert settings.window is not None
