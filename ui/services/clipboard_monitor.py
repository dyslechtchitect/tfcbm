"""DE-agnostic clipboard monitoring service using GTK4's Gdk.Clipboard.

Replaces the GNOME Shell extension's clipboard monitoring.
Polls the system clipboard every 250ms for changes and forwards
clipboard events to the server via the existing IPC mechanism.
"""

import asyncio
import base64
import hashlib
import json
import logging
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")

from gi.repository import Gdk, GLib, Gtk

logger = logging.getLogger("TFCBM.ClipboardMonitor")


class ClipboardMonitor:
    """Monitors the system clipboard for changes using GTK4's Gdk.Clipboard."""

    POLL_INTERVAL_MS = 250

    def __init__(self, on_clipboard_event):
        """
        Args:
            on_clipboard_event: Callback function receiving clipboard event dicts.
                                Event format: {'type': str, 'data': str, 'formatted_content': str|None}
        """
        self.on_clipboard_event = on_clipboard_event
        self._last_text_hash = None
        self._last_image_hash = None
        self._timeout_id = None
        self._running = False
        self._skip_next = True  # Skip the first check to avoid re-capturing existing clipboard
        self._clipboard = None

    def start(self):
        """Start clipboard monitoring."""
        if self._running:
            logger.warning("Clipboard monitor already running")
            return

        display = Gdk.Display.get_default()
        if not display:
            logger.error("No display available for clipboard monitoring")
            return

        self._clipboard = display.get_clipboard()
        self._running = True
        self._skip_next = True

        # Read current clipboard to establish baseline (don't send event for it)
        self._read_initial_clipboard()

        # Start polling
        self._timeout_id = GLib.timeout_add(self.POLL_INTERVAL_MS, self._poll_clipboard)
        logger.info("Clipboard monitor started (polling every %dms)", self.POLL_INTERVAL_MS)

    def stop(self):
        """Stop clipboard monitoring."""
        self._running = False
        if self._timeout_id is not None:
            GLib.source_remove(self._timeout_id)
            self._timeout_id = None
        logger.info("Clipboard monitor stopped")

    def _read_initial_clipboard(self):
        """Read current clipboard content to establish a baseline hash."""
        if not self._clipboard:
            return

        # Read text content to set initial hash
        self._clipboard.read_text_async(None, self._on_initial_text_read)

    def _on_initial_text_read(self, clipboard, result):
        """Handle initial text read to set baseline."""
        try:
            text = clipboard.read_text_finish(result)
            if text:
                self._last_text_hash = hashlib.md5(text.encode('utf-8', errors='replace')).hexdigest()
                logger.debug("Initial clipboard text hash: %s", self._last_text_hash)
        except Exception as e:
            logger.debug("No initial text in clipboard: %s", e)

    def _poll_clipboard(self):
        """Poll the clipboard for changes. Called by GLib timeout."""
        if not self._running or not self._clipboard:
            return False  # Stop the timeout

        if self._skip_next:
            self._skip_next = False
            return True  # Continue polling

        # Check clipboard content formats
        content = self._clipboard.get_formats()

        if content.contain_mime_type("text/plain") or content.contain_mime_type("UTF8_STRING") or content.contain_mime_type("text/plain;charset=utf-8"):
            self._clipboard.read_text_async(None, self._on_text_read)
        elif content.contain_mime_type("image/png") or content.contain_mime_type("image/jpeg"):
            # Read image data
            self._clipboard.read_texture_async(None, self._on_texture_read)

        return True  # Continue polling

    def _on_text_read(self, clipboard, result):
        """Handle text read from clipboard."""
        try:
            text = clipboard.read_text_finish(result)
            if not text:
                return

            text_hash = hashlib.md5(text.encode('utf-8', errors='replace')).hexdigest()

            if text_hash == self._last_text_hash:
                return  # No change

            self._last_text_hash = text_hash
            self._last_image_hash = None  # Reset image hash when text changes

            # Determine event type
            event_type = "text"
            stripped = text.strip()

            # Check if it's a URL
            if stripped.startswith(("http://", "https://", "ftp://", "file://")):
                event_type = "text"  # Still text type but could be detected as URL by server

            # Check if it's file URIs
            if stripped.startswith("file://") and "\n" in stripped:
                event_type = "file"

            event = {
                "type": event_type,
                "data": text,
                "formatted_content": None,
            }

            logger.info("Clipboard change detected: type=%s, length=%d", event_type, len(text))
            self.on_clipboard_event(event)

        except Exception as e:
            logger.debug("Error reading clipboard text: %s", e)

    def _on_texture_read(self, clipboard, result):
        """Handle texture (image) read from clipboard."""
        try:
            texture = clipboard.read_texture_finish(result)
            if not texture:
                return

            # Convert texture to PNG bytes
            png_bytes = texture.save_to_png_bytes()
            if not png_bytes:
                return

            data = png_bytes.get_data()
            image_hash = hashlib.md5(data).hexdigest()

            if image_hash == self._last_image_hash:
                return  # No change

            self._last_image_hash = image_hash
            self._last_text_hash = None  # Reset text hash when image changes

            # Encode as base64 data URI
            b64_data = base64.b64encode(data).decode('ascii')
            data_uri = f"data:image/png;base64,{b64_data}"

            event = {
                "type": "image/generic",
                "data": data_uri,
                "formatted_content": None,
            }

            logger.info("Clipboard image change detected: %d bytes", len(data))
            self.on_clipboard_event(event)

        except Exception as e:
            logger.debug("Error reading clipboard image: %s", e)
