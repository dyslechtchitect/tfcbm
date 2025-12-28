"""Clipboard operations service."""

import base64

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("GLib", "2.0")
gi.require_version("GObject", "2.0")
from gi.repository import Gdk, GLib, GObject


class ClipboardService:
    def __init__(self):
        self.clipboard = Gdk.Display.get_default().get_clipboard()

    def copy_text(self, text: str) -> None:
        """Copy plain text to clipboard."""
        self.clipboard.set(text)

    def copy_formatted_text(
        self, plain_text: str, formatted_content: str, format_type: str
    ) -> None:
        """Copy formatted text (HTML/RTF) to clipboard with fallback to plain text.

        Args:
            plain_text: Plain text version
            formatted_content: Base64-encoded formatted content
            format_type: Format type ('html' or 'rtf')
        """
        try:
            # Decode the base64 formatted content
            formatted_bytes = base64.b64decode(formatted_content)

            # Create content provider with multiple formats
            # Map format type to MIME type
            mime_type = "text/html" if format_type == "html" else "text/rtf"

            # Create GBytes from the formatted content
            formatted_gbytes = GLib.Bytes.new(formatted_bytes)

            # Set both formatted and plain text on clipboard
            # GTK will provide the appropriate format based on what the target supports
            content_provider = Gdk.ContentProvider.new_for_bytes(
                mime_type, formatted_gbytes
            )

            # Also add plain text as fallback
            plain_value = GObject.Value(str, plain_text)
            plain_provider = Gdk.ContentProvider.new_for_value(plain_value)

            # Union both providers so clipboard has both formats
            union_provider = Gdk.ContentProvider.new_union(
                [content_provider, plain_provider]
            )

            self.clipboard.set_content(union_provider)
        except Exception as e:
            # Fallback to plain text if formatted paste fails
            print(f"Failed to copy formatted text: {e}, falling back to plain text")
            self.copy_text(plain_text)

    def copy_image(self, texture: Gdk.Texture) -> None:
        """Copy image to clipboard."""
        self.clipboard.set_texture(texture)
