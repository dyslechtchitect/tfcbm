#!/usr/bin/env python3
"""
Clipboard Service - Processes clipboard events
"""
import base64
import json
import logging
import mimetypes
import re
import subprocess
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import unquote, urlparse

from server.src.services.database_service import DatabaseService
from server.src.services.thumbnail_service import ThumbnailService

logger = logging.getLogger(__name__)


class ClipboardService:
    """Service for processing clipboard events"""

    def __init__(self, database_service: DatabaseService, thumbnail_service: ThumbnailService):
        """
        Initialize clipboard service

        Args:
            database_service: Database service for storing clipboard data
            thumbnail_service: Thumbnail service for image processing
        """
        logger.info("[ClipboardService.__init__] Starting initialization...")
        self.db_service = database_service
        self.thumbnail_service = thumbnail_service
        # Keep in-memory history for legacy compatibility
        self.history = []
        logger.info("[ClipboardService.__init__] Initialization complete")

    def process_file(self, file_uri: str) -> Optional[Dict]:
        """
        Process a file URI and read its contents

        Args:
            file_uri: file:// URI from clipboard

        Returns:
            Dict with file metadata and content, or None if error
        """
        try:
            # Parse file URI to get path
            parsed = urlparse(file_uri)
            file_path = unquote(parsed.path)

            # Check if path exists
            path_obj = Path(file_path)
            if not path_obj.exists():
                logger.error(f"Path not found: {file_path}")
                return None

            # Handle directories
            if path_obj.is_dir():
                folder_name = path_obj.name
                metadata = {
                    'name': folder_name,
                    'size': 0,
                    'mime_type': 'inode/directory',
                    'extension': '',
                    'original_path': file_path,
                    'is_directory': True,
                }
                logger.info(f"Processed folder: {folder_name}")
                return {
                    'metadata': metadata,
                    'content': b''
                }

            # Handle regular files
            if not path_obj.is_file():
                logger.error(f"Not a file or directory: {file_path}")
                return None

            # Get file info
            file_name = path_obj.name
            file_size = path_obj.stat().st_size

            # Extract file extension
            file_extension = path_obj.suffix.lower()
            if not file_extension and file_name.startswith('.') and file_name.count('.') == 1:
                file_extension = file_name.lower()
            elif not file_extension and '.' in file_name:
                file_extension = '.' + file_name.split('.')[-1].lower()

            # Determine mime type
            mime_type, _ = mimetypes.guess_type(file_path)
            if not mime_type:
                file_lower = file_name.lower()
                if file_lower in ['.bashrc', '.zshrc', '.bash_profile', '.profile', '.bash_logout',
                                 '.zprofile', '.zshenv', '.zlogin', '.zlogout']:
                    mime_type = "application/x-shellscript"
                elif file_lower in ['.vimrc', '.nvimrc', '.editorconfig', '.gitignore',
                                   '.gitattributes', '.dockerignore', '.npmignore']:
                    mime_type = "text/plain"
                elif file_lower in ['.eslintrc', '.prettierrc', '.babelrc']:
                    mime_type = "application/json"
                elif file_lower.endswith('rc') and not file_lower.endswith('.src'):
                    mime_type = "text/plain"
                else:
                    try:
                        with open(file_path, 'rb') as test_file:
                            sample = test_file.read(512)
                            if b'\x00' not in sample:
                                try:
                                    sample.decode('utf-8')
                                    mime_type = "text/plain"
                                except UnicodeDecodeError:
                                    mime_type = "application/octet-stream"
                            else:
                                mime_type = "application/octet-stream"
                    except Exception:
                        mime_type = "application/octet-stream"

            # Read file contents (with size limit for safety)
            MAX_FILE_SIZE = 100 * 1024 * 1024
            if file_size > MAX_FILE_SIZE:
                logger.warning(f"File too large: {file_size} bytes (max: {MAX_FILE_SIZE})")
                return None

            try:
                with open(file_path, 'rb') as f:
                    file_content = f.read()
            except PermissionError as e:
                logger.error(f"Permission denied reading file: {file_path}")
                logger.error(f"  This may be due to Flatpak sandbox restrictions")
                logger.error(f"  Error: {e}")
                return None
            except OSError as e:
                logger.error(f"OS error reading file: {file_path}")
                logger.error(f"  Error: {e}")
                return None

            metadata = {
                'name': file_name,
                'size': file_size,
                'mime_type': mime_type,
                'extension': file_extension,
                'original_path': file_path,
                'is_directory': False,
            }

            logger.info(f"Processed file: {file_name} ({file_size} bytes, {mime_type})")

            return {
                'metadata': metadata,
                'content': file_content
            }

        except Exception as e:
            logger.error(f"Error processing file {file_uri}: {e}")
            return None

    def handle_clipboard_event(self, event_data: Dict):
        """
        Handle clipboard event from GNOME extension via DBus

        Args:
            event_data: Dictionary with clipboard event data from extension
                       Format: {"type": "text|image/...|file", "content": "..."}
        """
        try:
            event_type = event_data.get("type")
            content_data = event_data.get("content") or event_data.get("data")

            if not event_type or content_data is None:
                logger.warning("Invalid clipboard event: missing type or content")
                return

            logger.info(f"Processing clipboard event via DBus: {event_type}")

            if event_type == "text":
                self._handle_text(content_data, event_data)
            elif event_type.startswith("image/"):
                self._handle_image(event_type, content_data)
            elif event_type == "file":
                self._handle_file(content_data)

        except Exception as e:
            logger.error(f"Error handling clipboard event from DBus: {e}")
            logger.error(traceback.format_exc())

    def _handle_text(self, text: str, event_data: Dict):
        """Handle text clipboard event"""
        text_bytes = text.encode("utf-8")

        # Extract formatted content if present
        format_type = event_data.get("format_type") or event_data.get("formatType")
        formatted_content_b64 = event_data.get("formatted_content") or event_data.get("formattedContent")
        formatted_content = None

        if format_type and formatted_content_b64:
            formatted_content = base64.b64decode(formatted_content_b64)
            logger.info(f"  Detected {format_type} formatting ({len(formatted_content)} bytes)")

        # Check for URL
        url_pattern = re.compile(r'https?://\S+')
        is_url = url_pattern.search(text) is not None
        item_type = "url" if is_url else "text"

        # Calculate hash for deduplication
        text_hash = self.db_service.calculate_hash(text_bytes)
        timestamp = datetime.now().isoformat()

        existing_item_id = self.db_service.get_item_by_hash(text_hash)

        if existing_item_id:
            # Duplicate - update timestamp
            format_info = f" [{format_type}]" if format_type else ""
            logger.info(f"↻ Updating duplicate {item_type} ({len(text)} chars){format_info}")
            self.db_service.update_timestamp(existing_item_id, timestamp)
        else:
            # New item
            self.history.append({"type": item_type, "content": text, "timestamp": timestamp})

            self.db_service.add_item(
                item_type, text_bytes, timestamp,
                data_hash=text_hash,
                format_type=format_type,
                formatted_content=formatted_content
            )

            format_info = f" [{format_type}]" if format_type else ""
            logger.info(f"✓ Copied {item_type} ({len(text)} chars){format_info}")

    def _handle_image(self, event_type: str, content_data: str):
        """Handle image clipboard event"""
        image_content = json.loads(content_data)
        image_data_b64 = image_content.get("data")
        if not image_data_b64:
            logger.warning("Image event missing data field")
            return

        image_bytes = base64.b64decode(image_data_b64)
        image_hash = self.db_service.calculate_hash(image_bytes)
        timestamp = datetime.now().isoformat()

        existing_item_id = self.db_service.get_item_by_hash(image_hash)

        if existing_item_id:
            # Duplicate
            logger.info(f"↻ Updating duplicate image ({event_type}, {len(image_bytes)} bytes)")
            self.db_service.update_timestamp(existing_item_id, timestamp)
        else:
            # New image
            self.history.append({"type": event_type, "content": image_data_b64, "timestamp": timestamp})

            item_id = self.db_service.add_item(event_type, image_bytes, timestamp, data_hash=image_hash)

            # Generate thumbnail asynchronously
            self.thumbnail_service.process_thumbnail_async(item_id, image_bytes)

            logger.info(f"✓ Copied image ({event_type}, {len(image_bytes)} bytes)")

    def _handle_file(self, file_uris_raw: str):
        """Handle file clipboard event"""
        logger.info(f"Received file URI(s): {file_uris_raw[:200]}...")

        # Split by newlines and filter empty lines
        file_uris = [uri.strip() for uri in file_uris_raw.split('\n') if uri.strip()]
        logger.info(f"Processing {len(file_uris)} file(s)/folder(s)")

        # Process each file/folder
        for file_uri in file_uris:
            file_data = self.process_file(file_uri)

            if file_data:
                metadata = file_data['metadata']
                file_content = file_data['content']

                # Hash for deduplication
                if metadata.get('is_directory'):
                    hash_input = metadata['original_path'].encode('utf-8')
                else:
                    hash_input = file_content

                file_hash = self.db_service.calculate_hash(hash_input)
                timestamp = datetime.now().isoformat()

                existing_item_id = self.db_service.get_item_by_hash(file_hash)

                if existing_item_id:
                    logger.info("↻ Updating duplicate file/folder")
                    self.db_service.update_timestamp(existing_item_id, timestamp)
                else:
                    self.history.append({"type": "file", "content": file_uri, "timestamp": timestamp})

                    # Store as: metadata_json + separator + file_content
                    metadata_json = json.dumps(metadata).encode('utf-8')
                    separator = b'\n---FILE_CONTENT---\n'
                    combined_data = metadata_json + separator + file_content

                    self.db_service.add_item("file", combined_data, timestamp,
                                           data_hash=file_hash, name=metadata.get('name', 'unknown'))

                    logger.info(f"✓ Copied file/folder: {metadata.get('name', 'unknown')} (mime: {metadata.get('mime_type', 'unknown')})")
