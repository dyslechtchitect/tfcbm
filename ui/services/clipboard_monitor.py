"""DE-agnostic clipboard monitoring service using GTK4's Gdk.Clipboard.

Replaces the GNOME Shell extension's clipboard monitoring.
Listens for the Gdk.Clipboard 'changed' signal and forwards
clipboard events to the server via the existing IPC mechanism.

Does NOT rely on get_formats().contain_mime_type() for detection — it
returns False for everything on KDE Wayland.  Instead we try each read
method and cascade on failure: texture → uri-list → text.
"""

import base64
import hashlib
import json
import logging

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")

from gi.repository import Gdk, Gio, GLib, Gtk

logger = logging.getLogger("TFCBM.ClipboardMonitor")


class ClipboardMonitor:
    """Monitors the system clipboard for changes using GTK4's Gdk.Clipboard."""

    def __init__(self, on_clipboard_event):
        self.on_clipboard_event = on_clipboard_event
        self._last_text_hash = None
        self._last_image_hash = None
        self._last_uri_hash = None
        self._running = False
        self._skip_next = True
        self._clipboard = None
        self._changed_handler_id = None
        self._pending_text = None

    def start(self):
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

        # Baseline so we don't re-capture existing content
        self._clipboard.read_text_async(None, self._on_initial_text_read)

        self._changed_handler_id = self._clipboard.connect(
            "changed", self._on_clipboard_changed
        )
        logger.info("Clipboard monitor started (signal-based)")

    def stop(self):
        self._running = False
        if self._changed_handler_id is not None and self._clipboard:
            self._clipboard.disconnect(self._changed_handler_id)
            self._changed_handler_id = None
        logger.info("Clipboard monitor stopped")

    # ── signal handler ──────────────────────────────────────────────

    def _on_clipboard_changed(self, clipboard):
        if not self._running:
            return
        if self._skip_next:
            self._skip_next = False
            return
        # Small delay so the compositor finishes advertising formats
        GLib.timeout_add(50, self._try_read_texture)

    # ── cascade: texture → uri-list → text ──────────────────────────

    def _try_read_texture(self):
        """Step 1: try reading as an image (instant failure if not an image)."""
        if not self._running or not self._clipboard:
            return False
        self._clipboard.read_texture_async(None, self._on_texture_result)
        return False

    def _on_texture_result(self, clipboard, result):
        try:
            texture = clipboard.read_texture_finish(result)
        except Exception:
            texture = None

        if texture is not None:
            self._handle_texture(texture)
        else:
            # Not an image — try file URIs next
            self._try_read_uri_list()

    def _try_read_uri_list(self):
        if not self._running or not self._clipboard:
            return
        self._clipboard.read_async(
            ["text/uri-list"],
            GLib.PRIORITY_DEFAULT,
            None,
            self._on_uri_list_result,
        )

    def _on_uri_list_result(self, clipboard, result):
        try:
            stream, _mime = clipboard.read_finish(result)
        except Exception:
            stream = None

        if stream is not None:
            raw = self._read_stream(stream)
            uri_text = raw.decode("utf-8", errors="replace").strip() if raw else ""
            uris = [
                l.strip()
                for l in uri_text.splitlines()
                if l.strip().startswith("file://")
            ]
            if uris:
                self._handle_uris(uris, uri_text)
                return

        # Not file URIs — try plain text
        self._try_read_text()

    def _try_read_text(self):
        if not self._running or not self._clipboard:
            return
        self._clipboard.read_text_async(None, self._on_text_result)

    def _on_text_result(self, clipboard, result):
        try:
            text = clipboard.read_text_finish(result)
        except Exception:
            text = None

        if text:
            # Also try reading text/html for formatted content
            self._pending_text = text
            self._clipboard.read_async(
                ["text/html"],
                GLib.PRIORITY_DEFAULT,
                None,
                self._on_html_result,
            )
        else:
            logger.debug("Clipboard changed but no readable content found")

    def _on_html_result(self, clipboard, result):
        text = self._pending_text
        self._pending_text = None
        html_b64 = None

        try:
            stream, _mime = clipboard.read_finish(result)
            if stream:
                raw = self._read_stream(stream)
                if raw:
                    html_b64 = base64.b64encode(raw).decode("ascii")
        except Exception:
            pass

        self._handle_text(text, format_type="html" if html_b64 else None,
                          formatted_content=html_b64)

    # ── event builders ──────────────────────────────────────────────

    def _handle_texture(self, texture):
        png_bytes = texture.save_to_png_bytes()
        if not png_bytes:
            return
        data = png_bytes.get_data()

        image_hash = hashlib.md5(data).hexdigest()
        if image_hash == self._last_image_hash:
            return
        self._last_image_hash = image_hash
        self._last_text_hash = None
        self._last_uri_hash = None

        b64 = base64.b64encode(data).decode("ascii")
        event = {
            "type": "image/generic",
            "content": json.dumps({"data": b64}),
            "formatted_content": None,
        }
        logger.info("Clipboard image detected: %dx%d, %d bytes",
                     texture.get_width(), texture.get_height(), len(data))
        self.on_clipboard_event(event)

    def _handle_uris(self, uris, raw_text):
        uri_hash = hashlib.md5(raw_text.encode("utf-8")).hexdigest()
        if uri_hash == self._last_uri_hash:
            return
        self._last_uri_hash = uri_hash
        self._last_text_hash = None
        self._last_image_hash = None

        event = {
            "type": "file",
            "data": "\n".join(uris),
            "formatted_content": None,
        }
        logger.info("Clipboard file change detected: %d URI(s)", len(uris))
        self.on_clipboard_event(event)

    def _handle_text(self, text, format_type=None, formatted_content=None):
        text_hash = hashlib.md5(text.encode("utf-8", errors="replace")).hexdigest()
        if text_hash == self._last_text_hash:
            return
        self._last_text_hash = text_hash
        self._last_image_hash = None
        self._last_uri_hash = None

        event_type = "text"
        stripped = text.strip()
        if stripped.startswith("file://") and "\n" in stripped:
            event_type = "file"

        event = {
            "type": event_type,
            "data": text,
            "formatted_content": formatted_content,
        }
        if format_type:
            event["format_type"] = format_type
            event["formatType"] = format_type

        logger.info("Clipboard change detected: type=%s, length=%d, format=%s",
                     event_type, len(text), format_type or "plain")
        self.on_clipboard_event(event)

    # ── helpers ──────────────────────────────────────────────────────

    def _on_initial_text_read(self, clipboard, result):
        try:
            text = clipboard.read_text_finish(result)
            if text:
                self._last_text_hash = hashlib.md5(
                    text.encode("utf-8", errors="replace")
                ).hexdigest()
        except Exception:
            pass

    @staticmethod
    def _read_stream(stream):
        out = Gio.MemoryOutputStream.new_resizable()
        out.splice(
            stream,
            Gio.OutputStreamSpliceFlags.CLOSE_SOURCE
            | Gio.OutputStreamSpliceFlags.CLOSE_TARGET,
            None,
        )
        return out.steal_as_bytes().get_data()
