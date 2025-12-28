"""CSS loading service."""

from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gtk


class CssLoader:
    def load(self, css_path: str) -> bool:
        try:
            if not css_path or not Path(css_path).exists():
                return False

            provider = Gtk.CssProvider()
            provider.load_from_path(css_path)
            Gtk.StyleContext.add_provider_for_display(
                Gdk.Display.get_default(),
                provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )
            return True
        except Exception:
            return False
