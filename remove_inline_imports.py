#!/usr/bin/env python3
"""
Script to remove inline imports from Python files
Assumes imports are already at the top level
"""

import re
import sys

def remove_inline_imports(file_path):
    """Remove inline import statements that are already at top level"""

    with open(file_path, 'r') as f:
        lines = f.readlines()

    # List of imports to remove (already at top level)
    imports_to_remove = [
        'import asyncio',
        'import websockets',
        'import threading',
        'import traceback',
        'import time',
        'import os',
        'import signal',
        'import subprocess',
        'import argparse',
        'from datetime import datetime'
    ]

    new_lines = []
    for line in lines:
        # Check if this is an indented import statement
        stripped = line.strip()
        is_inline_import = False

        # Check if line starts with whitespace (indented)
        if line.startswith((' ', '\t')):
            # Check if it matches any of our imports to remove
            for import_str in imports_to_remove:
                if stripped == import_str:
                    is_inline_import = True
                    print(f"Removing inline import: {stripped}")
                    break

        if not is_inline_import:
            new_lines.append(line)

    # Write back
    with open(file_path, 'w') as f:
        f.writelines(new_lines)

    print(f"✓ Processed {file_path}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python remove_inline_imports.py <file>")
        sys.exit(1)

    remove_inline_imports(sys.argv[1])
