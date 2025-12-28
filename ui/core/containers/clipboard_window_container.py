"""Dependency injection container for the ClipboardWindow."""

from dataclasses import dataclass, field
from typing import Optional

from ui.services.websocket_client import WebSocketClient

from .app_container import AppContainer


@dataclass
class ClipboardWindowContainer:
    app_container: AppContainer

    _websocket_client: Optional[WebSocketClient] = field(default=None, init=False, repr=False)

    @property
    def websocket_client(self) -> WebSocketClient:
        if self._websocket_client is None:
            self._websocket_client = WebSocketClient(
                uri="ws://localhost:8765",
                max_size=5 * 1024 * 1024,
                on_message=self._on_websocket_message,  # This will be set by ClipboardWindow later
                on_error=self._on_websocket_error,  # This will be set by ClipboardWindow later
            )
        return self._websocket_client

    def _on_websocket_message(self, message):
        print(f"WS Message: {message}")  # This will be handled by ClipboardWindow

    def _on_websocket_error(self, error):
        print(f"WS Error: {error}")  # This will be handled by ClipboardWindow

    @classmethod
    def create(cls, app_container: AppContainer) -> "ClipboardWindowContainer":
        return cls(app_container=app_container)
