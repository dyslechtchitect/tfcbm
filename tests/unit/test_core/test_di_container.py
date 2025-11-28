"""Tests for dependency injection container."""

from pathlib import Path


def test_container_create_with_defaults():
    from ui.core.di_container import AppContainer

    container = AppContainer.create()

    assert container.settings is not None
    assert container.paths is not None


def test_container_create_with_custom_settings(tmp_path: Path):
    from ui.config import AppPaths, AppSettings, DisplaySettings, WindowSettings
    from ui.core.di_container import AppContainer

    settings = AppSettings(
        display=DisplaySettings(item_width=250),
        window=WindowSettings(default_width=400),
    )
    paths = AppPaths(
        db_path=tmp_path / "test.db",
        config_path=tmp_path / "config.yml",
        css_path=tmp_path / "style.css",
        resources_path=tmp_path / "res",
    )

    container = AppContainer.create(settings=settings, paths=paths)

    assert container.settings.display.item_width == 250
    assert container.paths.db_path == tmp_path / "test.db"


def test_container_db_service_lazy_initialization(tmp_path: Path):
    from ui.config import AppPaths
    from ui.core.di_container import AppContainer

    paths = AppPaths(
        db_path=tmp_path / "test.db",
        config_path=tmp_path / "config.yml",
        css_path=tmp_path / "style.css",
        resources_path=tmp_path / "res",
    )

    container = AppContainer.create(paths=paths)
    assert container._db_service is None

    db_service = container.db_service
    assert db_service is not None
    assert container._db_service is db_service


def test_container_db_service_singleton(tmp_path: Path):
    from ui.config import AppPaths
    from ui.core.di_container import AppContainer

    paths = AppPaths(
        db_path=tmp_path / "test.db",
        config_path=tmp_path / "config.yml",
        css_path=tmp_path / "style.css",
        resources_path=tmp_path / "res",
    )

    container = AppContainer.create(paths=paths)

    service1 = container.db_service
    service2 = container.db_service

    assert service1 is service2


def test_container_clipboard_service():
    import pytest
    from ui.core.di_container import AppContainer

    try:
        container = AppContainer.create()
        service = container.clipboard_service
        assert service is not None
    except AttributeError:
        pytest.skip("No display available for clipboard service")


def test_container_tag_service(tmp_path: Path):
    from ui.config import AppPaths
    from ui.core.di_container import AppContainer

    paths = AppPaths(
        db_path=tmp_path / "test.db",
        config_path=tmp_path / "config.yml",
        css_path=tmp_path / "style.css",
        resources_path=tmp_path / "res",
    )

    container = AppContainer.create(paths=paths)

    service = container.tag_service

    assert service is not None
