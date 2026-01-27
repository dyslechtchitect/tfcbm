"""Application paths configuration."""

import os
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
        ui_dir = Path(__file__).parent.parent

        # Use exact same logic as database.py for consistency
        # Flatpak / XDG-compliant data directory
        xdg_data_home = Path(
            os.environ.get(
                "XDG_DATA_HOME",
                Path.home() / ".local" / "share"
            )
        )

        app_id = "io.github.dyslechtchitect.tfcbm"
        db_dir = xdg_data_home / app_id
        db_path = db_dir / "clipboard.db"

        return cls(
            db_path=db_path,
            config_path=Path("settings.yml"),
            css_path=ui_dir / "style.css",
            resources_path=ui_dir.parent / "resouces",
        )
