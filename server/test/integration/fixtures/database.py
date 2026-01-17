"""Database fixtures for tests."""

import json
import pytest
import tempfile
from pathlib import Path
from typing import Generator

from database import ClipboardDB


@pytest.fixture
def temp_db() -> Generator[ClipboardDB, None, None]:
    """Create a temporary in-memory database for testing."""
    db = ClipboardDB(":memory:")
    yield db
    db.close()


@pytest.fixture
def temp_db_file() -> Generator[ClipboardDB, None, None]:
    """Create a temporary file-based database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    db = ClipboardDB(db_path)
    yield db
    db.close()

    # Clean up
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def populated_db(temp_db: ClipboardDB) -> ClipboardDB:
    """Create a database with sample data."""
    # Add text items
    temp_db.add_item("text", b"Hello World", timestamp="2025-01-01T10:00:00")
    temp_db.add_item("text", b"Python code snippet", timestamp="2025-01-01T11:00:00")
    temp_db.add_item("text", b"https://example.com", timestamp="2025-01-01T12:00:00")

    # Add image items
    temp_db.add_item("image/png", b"fake_png_data", thumbnail=b"thumbnail", timestamp="2025-01-02T10:00:00")
    temp_db.add_item("image/jpeg", b"fake_jpeg_data", thumbnail=b"thumbnail", timestamp="2025-01-02T11:00:00")

    # Add file item
    file_metadata = json.dumps({"name": "document.pdf", "extension": ".pdf", "size": 1024})
    file_data = file_metadata.encode() + b"\n---FILE_CONTENT---\n" + b"fake_pdf_content"
    temp_db.add_item("file", file_data, timestamp="2025-01-03T10:00:00", name="document.pdf")

    return temp_db
