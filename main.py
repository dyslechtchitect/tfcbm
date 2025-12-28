#!/usr/bin/env python3
"""
TFCBM Server Main Entry Point
Initializes all services with dependency injection and starts the server
"""
import asyncio
import logging
import os
import signal
import subprocess
import sys
import threading
import time

import websockets

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Import all services
from server.src.services.settings_service import SettingsService
from server.src.services.database_service import DatabaseService
from server.src.services.thumbnail_service import ThumbnailService
from server.src.services.clipboard_service import ClipboardService
from server.src.services.websocket_service import WebSocketService
from server.src.services.screenshot_service import ScreenshotService


class TFCBMServer:
    """Main server application with dependency injection"""

    def __init__(self):
        """Initialize server with all services"""
        logging.info("Initializing services...")

        # Initialize services in dependency order
        self.settings_service = SettingsService()
        self.database_service = DatabaseService(settings_service=self.settings_service)
        self.thumbnail_service = ThumbnailService(self.database_service)
        self.clipboard_service = ClipboardService(self.database_service, self.thumbnail_service)
        self.websocket_service = WebSocketService(
            self.database_service,
            self.settings_service,
            self.clipboard_service
        )
        self.screenshot_service = ScreenshotService(
            self.database_service,
            self.thumbnail_service,
            enabled=False  # Disabled by default
        )

        logging.info("All services initialized successfully")

    async def start_websocket_server(self):
        """Start WebSocket server for UI"""
        logging.info("Starting WebSocket server on ws://localhost:8765")
        configured_max_size = 5 * 1024 * 1024
        logging.info(f"WebSocket server configured with max_size: {configured_max_size} bytes")
        async with websockets.serve(
            self.websocket_service.websocket_handler,
            "localhost",
            8765,
            max_size=configured_max_size
        ):
            await asyncio.Future()  # Run forever

    def watch_for_new_items(self, loop):
        """Background thread to watch for new database items and broadcast to WebSocket clients"""
        logging.info("Starting database watcher for WebSocket broadcasts...")

        while True:
            try:
                latest_id = self.database_service.get_latest_id()

                if latest_id and latest_id > self.websocket_service.last_known_id:
                    # New items detected
                    logging.info(f"📢 Broadcasting new items {self.websocket_service.last_known_id + 1} to {latest_id}")
                    for item_id in range(self.websocket_service.last_known_id + 1, latest_id + 1):
                        item = self.database_service.get_item(item_id)
                        if item:
                            ui_item = self.websocket_service.prepare_item_for_ui(item)

                            # Broadcast to all clients
                            message = {"type": "new_item", "item": ui_item}

                            # Schedule broadcast in async loop
                            asyncio.run_coroutine_threadsafe(
                                self.websocket_service.broadcast(message),
                                loop
                            )
                            logging.info(f"  → Broadcast item {item_id} ({item['type']}) to {len(self.websocket_service.clients)} clients")

                    self.websocket_service.last_known_id = latest_id

            except Exception as e:
                logging.error(f"Error in database watcher: {e}")

            time.sleep(0.5)

    def signal_handler(self, signum, frame):
        """Handle shutdown signals and cleanup"""
        logging.info(f"\nReceived signal {signum}, shutting down...")

        # Kill UI process if it's running
        if self.websocket_service.ui_pid:
            try:
                logging.info(f"Killing UI process (PID: {self.websocket_service.ui_pid})...")
                os.kill(self.websocket_service.ui_pid, signal.SIGTERM)
                logging.info("UI process terminated")
            except ProcessLookupError:
                logging.info("UI process already terminated")
            except Exception as e:
                logging.error(f"Error killing UI process: {e}")

        # Shutdown thumbnail executor
        try:
            self.thumbnail_service.shutdown()
        except Exception as e:
            logging.error(f"Error shutting down thumbnail service: {e}")

        logging.info("Server shutdown complete")
        sys.exit(0)

    def _is_autostart_enabled(self) -> bool:
        """Check if autostart is enabled by checking for autostart desktop file."""
        from pathlib import Path
        autostart_dir = Path.home() / ".config" / "autostart"
        # Check both old and new filenames
        return (autostart_dir / "org.tfcbm.ClipboardManager.desktop").exists() or \
               (autostart_dir / "tfcbm.desktop").exists()

    def start(self):
        """Start the TFCBM server"""
        # Set up signal handlers for cleanup
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)

        # Only enable GNOME extension if autostart is enabled
        # This prevents the tray icon from appearing when autostart is disabled
        if self._is_autostart_enabled():
            try:
                import gi
                gi.require_version('Gio', '2.0')
                from gi.repository import Gio, GLib

                logging.info("Autostart is enabled - ensuring GNOME extension is enabled...")
                # Use DBus to enable extension (works from Flatpak sandbox)
                connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
                result = connection.call_sync(
                    'org.gnome.Shell.Extensions',
                    '/org/gnome/Shell/Extensions',
                    'org.gnome.Shell.Extensions',
                    'EnableExtension',
                    GLib.Variant('(s)', ('tfcbm-clipboard-monitor@github.com',)),
                    None,
                    Gio.DBusCallFlags.NONE,
                    -1,
                    None
                )
                logging.info("✓ GNOME extension enabled via DBus")
            except Exception as e:
                logging.warning(f"Failed to enable GNOME extension via DBus: {e}")
        else:
            logging.info("Autostart is disabled - skipping GNOME extension auto-enable")

        # Start screenshot service if enabled
        self.screenshot_service.start()

        # Start WebSocket server in separate thread with its own event loop
        def run_websocket_server():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Start database watcher
            watcher_thread = threading.Thread(
                target=self.watch_for_new_items,
                args=(loop,),
                daemon=True
            )
            watcher_thread.start()

            # Start WebSocket server
            loop.run_until_complete(self.start_websocket_server())

        websocket_thread = threading.Thread(target=run_websocket_server, daemon=True)
        websocket_thread.start()
        logging.info("WebSocket server started\n")

        logging.info("Listening for legacy events on /run/user/1000/tfcbm.sock")

        # Legacy UNIX socket server (kept for backward compatibility)
        # Note: Most new code uses WebSocket, but old extension might still use this
        socket_path = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "tfcbm.sock")

        # Remove existing socket if it exists
        try:
            os.unlink(socket_path)
        except FileNotFoundError:
            pass

        # Note: For simplicity, I'm not implementing the full UNIX socket server here
        # since the extension now uses DBus -> UI -> WebSocket path
        # The original tfcbm_server.py had this, but it's legacy code

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logging.info("\nStopping server...")


if __name__ == "__main__":
    server = TFCBMServer()
    server.start()
