"""Test data generators for TFCBM tests."""

import io
import json
import os
import random
import string
from datetime import datetime, timedelta
from typing import Tuple

from PIL import Image


def generate_random_text(length: int = 100) -> bytes:
    """Generate random text data."""
    text = ''.join(random.choices(string.ascii_letters + string.digits + ' \n', k=length))
    return text.encode('utf-8')


def generate_random_image(width: int = 100, height: int = 100, format: str = 'PNG') -> bytes:
    """Generate a random test image."""
    # Create random RGB image
    img = Image.new('RGB', (width, height))
    pixels = []
    for _ in range(width * height):
        pixels.append((
            random.randint(0, 255),
            random.randint(0, 255),
            random.randint(0, 255)
        ))
    img.putdata(pixels)

    # Save to bytes
    img_bytes = io.BytesIO()
    img.save(img_bytes, format=format)
    return img_bytes.getvalue()


def generate_file_data(filename: str, content: bytes = None, size: int = 1024) -> bytes:
    """
    Generate file data in the format expected by the database.

    Format: JSON metadata + separator + file content
    """
    if content is None:
        content = generate_random_text(size)

    # Extract extension from filename
    _, ext = os.path.splitext(filename)

    metadata = {
        "name": filename,
        "extension": ext,
        "size": len(content)
    }

    metadata_json = json.dumps(metadata)
    separator = b"\n---FILE_CONTENT---\n"

    return metadata_json.encode('utf-8') + separator + content


def generate_timestamp(days_ago: int = 0, hours_ago: int = 0) -> str:
    """Generate an ISO format timestamp relative to now."""
    dt = datetime.now() - timedelta(days=days_ago, hours=hours_ago)
    return dt.isoformat()


def create_text_items(count: int = 5) -> list[Tuple[str, bytes, str]]:
    """Create a list of text items (type, data, timestamp)."""
    items = []
    for i in range(count):
        item_type = "text"
        data = generate_random_text(random.randint(10, 200))
        timestamp = generate_timestamp(days_ago=i)
        items.append((item_type, data, timestamp))
    return items


def create_image_items(count: int = 3) -> list[Tuple[str, bytes, bytes, str]]:
    """Create a list of image items (type, data, thumbnail, timestamp)."""
    items = []
    formats = ['PNG', 'JPEG']
    for i in range(count):
        format_type = random.choice(formats)
        item_type = f"image/{format_type.lower()}"
        data = generate_random_image(format=format_type)
        thumbnail = generate_random_image(width=50, height=50, format='PNG')
        timestamp = generate_timestamp(days_ago=i)
        items.append((item_type, data, thumbnail, timestamp))
    return items


def create_file_items(count: int = 3) -> list[Tuple[str, bytes, str, str]]:
    """Create a list of file items (type, data, name, timestamp)."""
    items = []
    filenames = [
        "document.pdf",
        "archive.zip",
        "script.sh",
        "photo.jpg",
        "data.json",
        "notes.txt"
    ]

    for i in range(count):
        filename = random.choice(filenames)
        item_type = "file"
        data = generate_file_data(filename)
        timestamp = generate_timestamp(days_ago=i)
        items.append((item_type, data, filename, timestamp))
    return items
