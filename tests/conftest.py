"""Pytest configuration and shared fixtures."""

from pathlib import Path

import pytest


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture
def temp_config_path(tmp_path: Path) -> Path:
    return tmp_path / "settings.yml"


@pytest.fixture
def temp_css_path(tmp_path: Path) -> Path:
    css_path = tmp_path / "style.css"
    css_path.write_text("/* test css */")
    return css_path


@pytest.fixture
def temp_resources_path(tmp_path: Path) -> Path:
    resources = tmp_path / "resources"
    resources.mkdir()
    return resources
