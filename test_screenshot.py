#!/usr/bin/env python3
"""
Test script for screenshot capture functionality
"""

import base64
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path


def test_screenshot_capture():
    """Test that we can capture a screenshot"""
    print("Testing screenshot capture...")

    # Create temporary file
    temp_file = f"/tmp/test_screenshot_{int(time.time())}.png"

    try:
        # Capture screenshot using grim (Wayland)
        result = subprocess.run(["grim", temp_file], capture_output=True, timeout=5)

        if result.returncode == 0 and os.path.exists(temp_file):
            file_size = os.path.getsize(temp_file)
            print(f"✓ Screenshot captured successfully!")
            print(f"  File: {temp_file}")
            print(f"  Size: {file_size:,} bytes")

            # Test base64 encoding
            with open(temp_file, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")

            print(f"  Base64 size: {len(image_data):,} characters")

            # Clean up
            os.remove(temp_file)
            print("✓ Cleanup successful")

            return True
        else:
            print(f"✗ Screenshot capture failed")
            print(f"  Error: {result.stderr.decode() if result.stderr else 'Unknown'}")
            return False

    except subprocess.TimeoutExpired:
        print("✗ Screenshot capture timed out")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_screenshot_save():
    """Test saving screenshot to disk"""
    print("\nTesting screenshot save to disk...")

    save_dir = Path("./test_screenshots")
    save_dir.mkdir(exist_ok=True)

    timestamp = datetime.now()
    filename = f"screenshot_{timestamp.strftime('%Y%m%d_%H%M%S')}.png"
    filepath = save_dir / filename

    temp_file = f"/tmp/test_screenshot_{int(time.time())}.png"

    try:
        # Capture using grim (Wayland)
        result = subprocess.run(["grim", temp_file], capture_output=True, timeout=5)

        if result.returncode == 0:
            # Read, encode, decode, and save
            with open(temp_file, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")

            with open(filepath, "wb") as f:
                f.write(base64.b64decode(image_data))

            print(f"✓ Screenshot saved: {filepath}")
            print(f"  Size: {os.path.getsize(filepath):,} bytes")

            # Cleanup
            os.remove(temp_file)

            return True

    except Exception as e:
        print(f"✗ Error: {e}")
        return False


if __name__ == "__main__":
    print("TFCBM Screenshot Capture Test\n")
    print("=" * 50)

    # Run tests
    test1 = test_screenshot_capture()
    test2 = test_screenshot_save()

    print("\n" + "=" * 50)
    print("\nTest Results:")
    print(f"  Screenshot capture: {'✓ PASS' if test1 else '✗ FAIL'}")
    print(f"  Screenshot save:    {'✓ PASS' if test2 else '✗ FAIL'}")

    if test1 and test2:
        print("\n✓ All tests passed! Screenshot functionality is working.")
    else:
        print("\n✗ Some tests failed. Check the output above for details.")
