#!/usr/bin/env python3
"""Test if UI can render images"""

import base64
import traceback

import gi
from gi.repository import GdkPixbuf

from database import ClipboardDB

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")


def test_image_rendering():
    db = ClipboardDB()
    item = db.get_item(17)  # Image item

    print(f"Testing image rendering for item {item['id']}")
    print(f"Type: {item['type']}")
    print(f"Type starts with 'image/': {item['type'].startswith('image/')}")

    thumbnail = item.get("thumbnail")
    if thumbnail:
        print(f"Thumbnail size: {len(thumbnail)} bytes")

        try:
            # Encode to base64 (as the UI receives it)
            thumbnail_b64 = base64.b64encode(thumbnail).decode("utf-8")
            print(f"Base64 thumbnail size: {len(thumbnail_b64)}")

            # Decode base64 (as the UI does)
            image_data = base64.b64decode(thumbnail_b64)
            print(f"Decoded image size: {len(image_data)} bytes")

            # Try to load with GdkPixbufLoader (as the UI does)
            loader = GdkPixbuf.PixbufLoader()
            loader.write(image_data)
            loader.close()
            pixbuf = loader.get_pixbuf()

            if pixbuf:
                print(f"✓ Pixbuf loaded successfully!")
                print(f"  Size: {pixbuf.get_width()}x{pixbuf.get_height()}")
                print(f"  Has alpha: {pixbuf.get_has_alpha()}")
            else:
                print("✗ Pixbuf is None")

        except Exception as e:
            print(f"✗ Error: {e}")

            traceback.print_exc()
    else:
        print("✗ No thumbnail data")


if __name__ == "__main__":
    test_image_rendering()
