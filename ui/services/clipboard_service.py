"""Clipboard operations service."""

import gi

gi.require_version("Gdk", "4.0")
from gi.repository import Gdk


class ClipboardService:
    def __init__(self):
        self.clipboard = Gdk.Display.get_default().get_clipboard()

    def copy_text(self, text: str) -> None:
        self.clipboard.set(text)

    def copy_image(self, texture: Gdk.Texture) -> None:
        self.clipboard.set_texture(texture)
