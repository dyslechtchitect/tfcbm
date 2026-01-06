#!/usr/bin/env python3
import os
import sys
import zipfile
from pathlib import Path

def create_extension_zip(source_root, output_file):
    """Create extension zip file"""
    ext_dir = Path(source_root) / 'gnome-extension'

    # Files and directories to exclude
    exclude = {'.md', '.sh', 'test', 'package.json'}

    with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(ext_dir):
            # Remove excluded directories from walk
            dirs[:] = [d for d in dirs if d not in exclude]

            for file in files:
                # Skip excluded files
                if any(file.endswith(ext) for ext in exclude if ext.startswith('.')):
                    continue
                if file in exclude:
                    continue

                file_path = Path(root) / file
                arcname = file_path.relative_to(ext_dir)
                zipf.write(file_path, arcname)

    print(f"Created {output_file}")

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <source_root> <output_file>")
        sys.exit(1)

    create_extension_zip(sys.argv[1], sys.argv[2])
