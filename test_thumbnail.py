#!/usr/bin/env python3
"""Test thumbnail generation"""

import base64
from database import ClipboardDB
from tfcbm_server import generate_thumbnail

# Create test image (simple PNG)
test_image_b64 = """
iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==
"""

image_data = base64.b64decode(test_image_b64.strip())

print("Testing thumbnail generation...")
print(f"Original image: {len(image_data)} bytes")

thumbnail = generate_thumbnail(image_data, max_size=250)

if thumbnail:
    print(f"Thumbnail generated: {len(thumbnail)} bytes")
    print("✓ Thumbnail generation works!")
else:
    print("✗ Thumbnail generation failed")

# Test database
print("\nTesting database with thumbnail...")
db = ClipboardDB()

item_id = db.add_item('image/png', image_data, thumbnail=thumbnail)
print(f"Added item {item_id} with thumbnail")

item = db.get_item(item_id)
if item and item['thumbnail']:
    print(f"✓ Thumbnail stored: {len(item['thumbnail'])} bytes")
else:
    print("✗ Thumbnail not stored")

db.close()
