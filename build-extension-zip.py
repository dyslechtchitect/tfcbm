#!/usr/bin/env python3
import os
import sys
import zipfile
from pathlib import Path

def create_extension_zip(source_root, output_file):
    """Create extension zip file"""
    ext_dir = Path(source_root) / 'gnome-extension'

    # Files and directories to exclude
    exclude_dirs = {'test', '.flatpak-builder', '.idea', '.claude', '__pycache__', '.git'}
    exclude_files = {'package.json', 'install.sh', 'uninstall.sh'}
    exclude_patterns = {'.md', '.sh', '.pyc', '.gitignore'}

    with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(ext_dir):
            # Remove excluded directories and hidden directories from walk
            dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith('.')]

            for file in files:
                # Skip excluded files and patterns
                if file in exclude_files:
                    continue
                if file.startswith('.'):
                    continue
                if any(file.endswith(ext) for ext in exclude_patterns):
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
