"""Text highlighting utilities."""

import re

import gi

gi.require_version("GLib", "2.0")
from gi.repository import GLib


def highlight_text(text: str, query: str) -> str:
    if not query or not text:
        return GLib.markup_escape_text(text) if text else ""

    escaped_text = GLib.markup_escape_text(text)
    escaped_query = re.escape(query)

    def replace_match(match):
        return (
            f'<span background="yellow" foreground="black">'
            f"{match.group(0)}</span>"
        )

    highlighted = re.sub(
        f"({escaped_query})",
        replace_match,
        escaped_text,
        flags=re.IGNORECASE,
    )
    return highlighted
