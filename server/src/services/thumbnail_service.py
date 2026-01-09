#!/usr/bin/env python3
"""
Thumbnail Service - Handles thumbnail generation for images using GdkPixbuf
"""
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import gi
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import GdkPixbuf, GLib

from server.src.services.database_service import DatabaseService

logger = logging.getLogger(__name__)


class ThumbnailService:
    """Service for generating image thumbnails asynchronously"""

    def __init__(self, database_service: DatabaseService, max_workers: int = 2):
        """
        Initialize thumbnail service

        Args:
            database_service: Database service for storing thumbnails
            max_workers: Maximum number of worker threads
        """
        logger.info("[ThumbnailService.__init__] Starting initialization...")
        self.db_service = database_service
        logger.info("[ThumbnailService.__init__] Creating ThreadPoolExecutor...")
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="thumbnail")
        logger.info("[ThumbnailService.__init__] Initialization complete")

    def generate_thumbnail(self, image_data: bytes, max_size: int = 250) -> Optional[bytes]:
        """
        Generate a thumbnail from image data using GdkPixbuf

        Args:
            image_data: Original image bytes
            max_size: Maximum width/height (maintains aspect ratio)

        Returns:
            Thumbnail image bytes (PNG format) or None on error
        """
        try:
            # Load image from bytes using GdkPixbuf
            loader = GdkPixbuf.PixbufLoader()
            loader.write(image_data)
            loader.close()
            pixbuf = loader.get_pixbuf()

            if pixbuf is None:
                logger.error("Failed to load image data")
                return None

            # Get original dimensions
            orig_width = pixbuf.get_width()
            orig_height = pixbuf.get_height()

            # Calculate thumbnail size maintaining aspect ratio
            if orig_width > orig_height:
                new_width = max_size
                new_height = int((max_size / orig_width) * orig_height)
            else:
                new_height = max_size
                new_width = int((max_size / orig_height) * orig_width)

            # Scale the pixbuf
            thumbnail = pixbuf.scale_simple(
                new_width,
                new_height,
                GdkPixbuf.InterpType.BILINEAR
            )

            if thumbnail is None:
                logger.error("Failed to scale image")
                return None

            # Save to bytes as PNG
            success, buffer = thumbnail.save_to_bufferv('png', [], [])

            if not success:
                logger.error("Failed to save thumbnail to buffer")
                return None

            thumbnail_bytes = bytes(buffer)
            logger.info(f"Generated thumbnail: {orig_width}x{orig_height} -> {new_width}x{new_height} ({len(thumbnail_bytes)} bytes)")
            return thumbnail_bytes

        except GLib.Error as e:
            logger.error(f"GdkPixbuf error generating thumbnail: {e}")
            return None
        except Exception as e:
            logger.error(f"Error generating thumbnail: {e}")
            return None

    def process_thumbnail_async(self, item_id: int, image_data: bytes):
        """
        Process thumbnail in background thread

        Args:
            item_id: Database item ID
            image_data: Original image bytes
        """
        def worker():
            try:
                thumbnail = self.generate_thumbnail(image_data)
                if thumbnail:
                    self.db_service.update_thumbnail(item_id, thumbnail)
                    logger.info(f"✓ Thumbnail saved for item {item_id}")
            except Exception as e:
                logger.error(f"Error in thumbnail worker: {e}")

        # Submit to thread pool
        self.executor.submit(worker)

    def shutdown(self):
        """Shutdown the executor"""
        self.executor.shutdown(wait=True)
