"""
Pytest configuration and shared fixtures for TFCBM backend tests.
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

# Add server/src to path for production code imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
# Add test/integration to path for fixtures imports
sys.path.insert(0, str(Path(__file__).parent))
