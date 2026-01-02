"""WebSocket client compatibility wrapper - redirects to IPC client.

This module provides backward compatibility by re-exporting IPCClient as WebSocketClient.
All existing code that imports WebSocketClient will transparently use the UNIX socket IPC client.
"""

from ui.services.ipc_client import IPCClient

# Re-export IPCClient as WebSocketClient for backward compatibility
WebSocketClient = IPCClient

__all__ = ["WebSocketClient"]
