"""Application paths configuration."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppPaths:
    db_path: Path
    config_path: Path
    css_path: Path
    resources_path: Path

    @classmethod
    def default(cls) -> "AppPaths":
        home = Path.home()
        ui_dir = Path(__file__).parent.parent

        return cls(
            db_path=home / ".local" / "share" / "tfcbm" / "clipboard.db",
            config_path=Path("settings.yml"),
            css_path=ui_dir / "style.css",
            resources_path=ui_dir.parent / "resouces",
        )
