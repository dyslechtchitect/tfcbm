#!/usr/bin/env python3
"""
One-time maintenance script to clean up orphaned recently_pasted records.

This script fixes the issue where the pasted tab shows "2 out of 647 items"
because 645 orphaned records exist that reference deleted clipboard items.

Root cause: Foreign keys weren't enabled in SQLite, so CASCADE delete didn't work.
Fix applied: Foreign keys now enabled + manual cleanup added to delete methods.

This script is safe to run multiple times.
"""

import sys
from pathlib import Path

# Add src to path to import database module
sys.path.insert(0, str(Path(__file__).parent / "src"))

from database import ClipboardDB


def main():
    print("=== TFCBM Orphaned Records Cleanup ===")
    print()

    # Connect to the database
    db = ClipboardDB()

    print(f"Database: {db.db_path}")
    print()

    # Get current counts
    total_items = db.get_total_count()
    pasted_count_before = db.get_pasted_count()

    print(f"Total clipboard items: {total_items}")
    print(f"Valid pasted records: {pasted_count_before}")
    print()

    # Run the cleanup
    print("Running cleanup...")
    orphaned_count = db._cleanup_orphaned_pasted_records()

    print()
    print("=== Results ===")
    print(f"✅ Cleaned up {orphaned_count} orphaned records")

    # Get new counts
    pasted_count_after = db.get_pasted_count()
    print(f"Valid pasted records after cleanup: {pasted_count_after}")
    print()

    if orphaned_count > 0:
        print(f"The pasted tab should now show: {pasted_count_after} items")
        print("(instead of the previous incorrect count)")
    else:
        print("No orphaned records found - database is clean!")

    print()
    print("✨ Done!")


if __name__ == "__main__":
    main()
