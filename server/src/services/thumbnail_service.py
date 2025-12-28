#!/usr/bin/env python3
"""
Thumbnail Service - Handles thumbnail generation for images
"""
import logging
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from typing import Optional

from PIL import Image

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
        Generate a thumbnail from image data

        Args:
            image_data: Original image bytes
            max_size: Maximum width/height (maintains aspect ratio)

        Returns:
            Thumbnail image bytes (PNG format) or None on error
        """
        try:
            # Open image from bytes
            image = Image.open(BytesIO(image_data))

            # Convert RGBA to RGB if needed (for JPEG compatibility)
            if image.mode in ("RGBA", "LA", "P"):
                background = Image.new("RGB", image.size, (255, 255, 255))
                if image.mode == "P":
                    image = image.convert("RGBA")
                background.paste(image, mask=image.split()[-1] if image.mode in ("RGBA", "LA") else None)
                image = background

            # Calculate thumbnail size maintaining aspect ratio
            image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

            # Save to bytes
            thumbnail_io = BytesIO()
            image.save(thumbnail_io, format="PNG", optimize=True)
            thumbnail_bytes = thumbnail_io.getvalue()

            logger.info(f"Generated thumbnail: {image.size} -> {len(thumbnail_bytes)} bytes")
            return thumbnail_bytes

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
