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
from server.src.services.ipc_service import IPCService
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
        self.ipc_service = IPCService(
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

    async def start_ipc_server(self):
        """Start UNIX domain socket IPC server for UI"""
        socket_path = self.ipc_service.socket_path

        # Remove existing socket if it exists
        try:
            os.unlink(socket_path)
        except FileNotFoundError:
            pass

        logging.info(f"Starting IPC server on {socket_path}")
        server = await asyncio.start_unix_server(
            self.ipc_service.client_handler,
            socket_path
        )

        # Set socket permissions to allow only user access
        os.chmod(socket_path, 0o600)

        async with server:
            await server.serve_forever()

    def watch_for_new_items(self, loop):
        """Background thread to watch for new database items and broadcast to IPC clients"""
        logging.info("Starting database watcher for IPC broadcasts...")

        while True:
            try:
                latest_id = self.database_service.get_latest_id()

                if latest_id and latest_id > self.ipc_service.last_known_id:
                    # New items detected
                    logging.info(f"📢 Broadcasting new items {self.ipc_service.last_known_id + 1} to {latest_id}")
                    for item_id in range(self.ipc_service.last_known_id + 1, latest_id + 1):
                        item = self.database_service.get_item(item_id)
                        if item:
                            ui_item = self.ipc_service.prepare_item_for_ui(item)

                            # Broadcast to all clients
                            message = {"type": "new_item", "item": ui_item}

                            # Schedule broadcast in async loop
                            asyncio.run_coroutine_threadsafe(
                                self.ipc_service.broadcast(message),
                                loop
                            )
                            logging.info(f"  → Broadcast item {item_id} ({item['type']}) to {len(self.ipc_service.clients)} clients")

                    self.ipc_service.last_known_id = latest_id

            except Exception as e:
                logging.error(f"Error in database watcher: {e}")

            time.sleep(0.5)

    def signal_handler(self, signum, frame):
        """Handle shutdown signals and cleanup"""
        logging.info(f"\nReceived signal {signum}, shutting down...")

        # Kill UI process if it's running
        if self.ipc_service.ui_pid:
            try:
                logging.info(f"Killing UI process (PID: {self.ipc_service.ui_pid})...")
                os.kill(self.ipc_service.ui_pid, signal.SIGTERM)
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

        # Clean up IPC socket
        try:
            os.unlink(self.ipc_service.socket_path)
            logging.info("IPC socket removed")
        except FileNotFoundError:
            pass
        except Exception as e:
            logging.error(f"Error removing IPC socket: {e}")

        logging.info("Server shutdown complete")
        sys.exit(0)

    def _is_autostart_enabled(self) -> bool:
        """Check if autostart is enabled by checking for autostart desktop file."""
        from pathlib import Path
        autostart_dir = Path.home() / ".config" / "autostart"
        autostart_file = autostart_dir / "io.github.dyslechtchitect.tfcbm.desktop"
        return autostart_file.exists()

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

        # Start IPC server in separate thread with its own event loop
        def run_ipc_server():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Start database watcher
            watcher_thread = threading.Thread(
                target=self.watch_for_new_items,
                args=(loop,),
                daemon=True
            )
            watcher_thread.start()

            # Start IPC server
            loop.run_until_complete(self.start_ipc_server())

        ipc_thread = threading.Thread(target=run_ipc_server, daemon=True)
        ipc_thread.start()
        logging.info("IPC server started\n")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logging.info("\nStopping server...")


if __name__ == "__main__":
    server = TFCBMServer()
    server.start()
