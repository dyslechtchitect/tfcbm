"""Dependency injection container for the ClipboardWindow."""

from dataclasses import dataclass, field
from typing import Optional

from ui.services.ipc_client import IPCClient

from .app_container import AppContainer


@dataclass
class ClipboardWindowContainer:
    app_container: AppContainer

    _ipc_client: Optional[IPCClient] = field(default=None, init=False, repr=False)

    @property
    def ipc_client(self) -> IPCClient:
        if self._ipc_client is None:
            self._ipc_client = IPCClient(
                on_message=self._on_ipc_message,  # This will be set by ClipboardWindow later
                on_error=self._on_ipc_error,  # This will be set by ClipboardWindow later
            )
        return self._ipc_client

    # Backward compatibility alias
    @property
    def ipc_client(self) -> IPCClient:
        """Backward compatibility property - returns IPC client."""
        return self.ipc_client

    def _on_ipc_message(self, message):
        print(f"IPC Message: {message}")  # This will be handled by ClipboardWindow

    def _on_ipc_error(self, error):
        print(f"IPC Error: {error}")  # This will be handled by ClipboardWindow

    @classmethod
    def create(cls, app_container: AppContainer) -> "ClipboardWindowContainer":
        return cls(app_container=app_container)
