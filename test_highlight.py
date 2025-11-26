#!/usr/bin/env python3
"""Test the highlight_text function"""

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import GLib
import re


def highlight_text(text, query):
    """
    Highlight matching text with yellow background using Pango markup.
    Returns escaped markup with highlights.
    """
    if not query or not text:
        # Escape the text for markup but don't highlight
        return GLib.markup_escape_text(text)

    # Escape the text first
    escaped_text = GLib.markup_escape_text(text)
    escaped_query = re.escape(query)

    # Use regex to find all matches (case-insensitive)
    def replace_match(match):
        return f'<span background="yellow" foreground="black">{match.group(0)}</span>'

    # Highlight all matches
    highlighted = re.sub(f'({escaped_query})', replace_match, escaped_text, flags=re.IGNORECASE)
    return highlighted


# Test cases
print("Test 1: Basic highlighting")
result = highlight_text("Hello World", "world")
print(f"Input: 'Hello World', Query: 'world'")
print(f"Output: {result}")
print()

print("Test 2: Multiple matches")
result = highlight_text("The quick brown fox jumps over the lazy dog", "the")
print(f"Input: 'The quick brown fox jumps over the lazy dog', Query: 'the'")
print(f"Output: {result}")
print()

print("Test 3: No match")
result = highlight_text("Hello World", "xyz")
print(f"Input: 'Hello World', Query: 'xyz'")
print(f"Output: {result}")
print()

print("Test 4: Empty query")
result = highlight_text("Hello World", "")
print(f"Input: 'Hello World', Query: ''")
print(f"Output: {result}")
print()

print("Test 5: Special characters in text")
result = highlight_text("Price: $50 & tax", "50")
print(f"Input: 'Price: $50 & tax', Query: '50'")
print(f"Output: {result}")
