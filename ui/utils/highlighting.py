"""Text highlighting utilities."""

import re

import gi

gi.require_version("GLib", "2.0")
from gi.repository import GLib


def highlight_text(text: str, query: str) -> str:
    """
    Highlight search terms in text.

    Supports:
    - Multiple words: highlights each word separately (e.g., "foo bar" highlights both)
    - Quoted phrases: highlights exact phrase (e.g., '"foo bar"' highlights the phrase)
    - Mixed: can combine both (e.g., '"exact phrase" word1 word2')
    """
    if not query or not text:
        return GLib.markup_escape_text(text) if text else ""

    escaped_text = GLib.markup_escape_text(text)
    query = query.strip()

    # Parse query into individual words and quoted phrases
    # Example: hello "world foo" bar → ["hello", "world foo", "bar"]
    if query.startswith('"') and query.endswith('"') and query.count('"') == 2:
        # Single quoted phrase - match exactly
        search_terms = [query[1:-1]]
    else:
        # Split on spaces but keep quoted phrases together
        # First, find all matches (quoted strings or words)
        parts = re.findall(r'"[^"]+"|\S+', query)
        # Strip quotes from quoted parts
        search_terms = [p.strip('"') for p in parts]

    # Build regex pattern that matches any of the search terms
    # Escape each term for regex safety
    escaped_terms = [re.escape(term) for term in search_terms if term]

    if not escaped_terms:
        return escaped_text

    # Create pattern that matches any of the terms (case-insensitive)
    pattern = "|".join(f"({term})" for term in escaped_terms)

    def replace_match(match):
        return (
            f'<span background="yellow" foreground="black">'
            f"{match.group(0)}</span>"
        )

    highlighted = re.sub(
        pattern,
        replace_match,
        escaped_text,
        flags=re.IGNORECASE,
    )
    return highlighted
