"""Icon utilities for file type detection."""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Gio", "2.0")
from gi.repository import Gdk, Gio, Gtk


def get_file_icon(file_name: str, mime_type: str, is_directory: bool) -> str:
    if is_directory:
        return "folder"

    icon_name = None
    try:
        content_type = Gio.content_type_guess(file_name, None)[0]
        if content_type:
            icon = Gio.content_type_get_icon(content_type)
            if isinstance(icon, Gio.ThemedIcon):
                icon_names = icon.get_names()
                theme = Gtk.IconTheme.get_for_display(
                    Gdk.Display.get_default()
                )
                for name in icon_names:
                    if theme.has_icon(name):
                        icon_name = name
                        break
    except Exception:
        pass

    if not icon_name and mime_type:
        try:
            content_type = Gio.content_type_from_mime_type(mime_type)
            if content_type:
                icon = Gio.content_type_get_icon(content_type)
                if isinstance(icon, Gio.ThemedIcon):
                    icon_names = icon.get_names()
                    theme = Gtk.IconTheme.get_for_display(
                        Gdk.Display.get_default()
                    )
                    for name in icon_names:
                        if theme.has_icon(name):
                            icon_name = name
                            break
        except Exception:
            pass

    return icon_name or "text-x-generic"
