"""Dependency injection container."""

from dataclasses import dataclass, field
from typing import Optional

from ui.config import AppPaths, AppSettings
from ui.services import ClipboardService, DatabaseService, TagService


@dataclass
class AppContainer:
    settings: AppSettings
    paths: AppPaths

    _db_service: Optional[DatabaseService] = field(
        default=None, init=False, repr=False
    )
    _clipboard_service: Optional[ClipboardService] = field(
        default=None, init=False, repr=False
    )
    _tag_service: Optional[TagService] = field(
        default=None, init=False, repr=False
    )

    @property
    def db_service(self) -> DatabaseService:
        if self._db_service is None:
            self._db_service = DatabaseService(str(self.paths.db_path))
        return self._db_service

    @property
    def clipboard_service(self) -> ClipboardService:
        if self._clipboard_service is None:
            self._clipboard_service = ClipboardService()
        return self._clipboard_service

    @property
    def tag_service(self) -> TagService:
        if self._tag_service is None:
            self._tag_service = TagService(self.db_service.db)
        return self._tag_service

    @classmethod
    def create(
        cls,
        settings: Optional[AppSettings] = None,
        paths: Optional[AppPaths] = None,
    ) -> "AppContainer":
        return cls(
            settings=settings or AppSettings.load(),
            paths=paths or AppPaths.default(),
        )
