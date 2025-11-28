"""Tests for paths configuration."""

from pathlib import Path


def test_app_paths_default():
    from ui.config.paths import AppPaths

    paths = AppPaths.default()

    assert paths.db_path.name == "clipboard.db"
    assert "tfcbm" in str(paths.db_path)
    assert paths.config_path.name == "settings.yml"
    assert paths.css_path.name == "style.css"
    assert paths.resources_path.name == "resouces"


def test_app_paths_custom(tmp_path: Path):
    from ui.config.paths import AppPaths

    paths = AppPaths(
        db_path=tmp_path / "test.db",
        config_path=tmp_path / "config.yml",
        css_path=tmp_path / "custom.css",
        resources_path=tmp_path / "res",
    )

    assert paths.db_path == tmp_path / "test.db"
    assert paths.config_path == tmp_path / "config.yml"
    assert paths.css_path == tmp_path / "custom.css"
    assert paths.resources_path == tmp_path / "res"


def test_app_paths_immutable():
    from ui.config.paths import AppPaths
    import pytest

    paths = AppPaths.default()

    with pytest.raises(AttributeError):
        paths.db_path = Path("/new/path")
