#!/usr/bin/env python3
"""
Screenshot Service - Captures periodic screenshots (disabled by default)
"""
import base64
import logging
import os
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

from server.src.services.database_service import DatabaseService
from server.src.services.thumbnail_service import ThumbnailService

logger = logging.getLogger(__name__)


class ScreenshotService:
    """Service for capturing periodic screenshots"""

    def __init__(self, database_service: DatabaseService, thumbnail_service: ThumbnailService,
                 enabled: bool = False, interval: int = 30, save_dir: str = None):
        """
        Initialize screenshot service

        Args:
            database_service: Database service for storing screenshots
            thumbnail_service: Thumbnail service for screenshot thumbnails
            enabled: Whether screenshot capture is enabled
            interval: Interval between screenshots in seconds
            save_dir: Optional directory to save screenshots to disk
        """
        logger.info("[ScreenshotService.__init__] Starting initialization...")
        self.db_service = database_service
        self.thumbnail_service = thumbnail_service
        self.enabled = enabled
        self.interval = interval
        self.save_dir = save_dir
        self.worker_thread = None
        logger.info("[ScreenshotService.__init__] Initialization complete")

    def start(self):
        """Start screenshot capture worker thread"""
        if not self.enabled:
            logger.info("Screenshot capture disabled, not starting worker")
            return

        logger.info(f"📸 Screenshot capture started (interval: {self.interval}s)")

        if self.save_dir:
            Path(self.save_dir).mkdir(parents=True, exist_ok=True)
            logger.info(f"📁 Saving screenshots to: {self.save_dir}")

        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()

    def _worker(self):
        """Background thread that captures screenshots at regular intervals"""
        while self.enabled:
            try:
                time.sleep(self.interval)

                # Capture screenshot
                image_data = self._capture_screenshot()

                if image_data:
                    timestamp = datetime.now()
                    timestamp_str = timestamp.isoformat()

                    # Save to database
                    image_bytes = base64.b64decode(image_data)
                    item_id = self.db_service.add_item("screenshot", image_bytes, timestamp_str)

                    # Generate thumbnail asynchronously
                    self.thumbnail_service.process_thumbnail_async(item_id, image_bytes)

                    # Optionally save to disk
                    if self.save_dir:
                        filename = f"screenshot_{timestamp.strftime('%Y%m%d_%H%M%S')}.png"
                        filepath = Path(self.save_dir) / filename

                        with open(filepath, "wb") as f:
                            f.write(base64.b64decode(image_data))

                        logger.info(f"📸 Screenshot captured and saved: {filename}")
                    else:
                        logger.info(f"📸 Screenshot captured ({len(image_data)} bytes)")

            except Exception as e:
                logger.error(f"⚠ Screenshot worker error: {e}")

    def _capture_screenshot(self):
        """Capture a full-screen screenshot using grim (Wayland screenshot tool)"""
        try:
            # Create temporary file for screenshot
            temp_file = f"/tmp/tfcbm_screenshot_{int(time.time())}.png"

            # Capture screenshot using grim (Wayland-native tool)
            result = subprocess.run(["grim", temp_file], capture_output=True, timeout=5)

            if result.returncode == 0 and os.path.exists(temp_file):
                # Read screenshot and encode as base64
                with open(temp_file, "rb") as f:
                    image_data = base64.b64encode(f.read()).decode("utf-8")

                # Clean up temp file
                os.remove(temp_file)

                return image_data
            else:
                logger.warning(
                    f"Screenshot capture failed: {result.stderr.decode() if result.stderr else 'Unknown error'}"
                )
                return None

        except subprocess.TimeoutExpired:
            logger.warning("Screenshot capture timed out")
            return None
        except Exception as e:
            logger.error(f"Screenshot error: {e}")
            return None
