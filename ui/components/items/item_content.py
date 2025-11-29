"""Item content display component."""

import base64

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, Gtk, Pango

from ui.utils import format_size, get_file_icon, highlight_text


class ItemContent:
    def __init__(self, item: dict, search_query: str = ""):
        self.item = item
        self.search_query = search_query
        self.item_type = item.get("type", "unknown")

    def build(self) -> Gtk.Widget:
        content_clamp = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content_clamp.set_vexpand(False)
        content_clamp.set_hexpand(True)
        content_clamp.set_overflow(Gtk.Overflow.HIDDEN)

        if self.item_type == "text" or self.item_type == "url":
            widget = self._build_text_content()
        elif self.item_type == "file":
            widget = self._build_file_content()
        elif (
            self.item_type.startswith("image/")
            or self.item_type == "screenshot"
        ):
            widget = self._build_image_content()
        else:
            widget = self._build_unknown_content()

        content_clamp.append(widget)
        return content_clamp

    def _build_text_content(self) -> Gtk.Widget:
        container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        container.set_vexpand(False)
        container.set_hexpand(True)
        container.set_overflow(Gtk.Overflow.HIDDEN)
        container.set_margin_bottom(40)  # Space for tags overlay

        content_label = Gtk.Label()

        # Add quotes inline with the text content
        text_content = self.item["content"]
        open_quote = '<span size="larger" alpha="60%">\u201c</span>'
        close_quote = '<span size="larger" alpha="60%">\u201d</span>'

        if self.search_query:
            # Highlight search terms in the content
            highlighted = highlight_text(text_content, self.search_query)
            # Add quotes around the highlighted content
            markup = f"{open_quote}{highlighted}{close_quote}"
            content_label.set_markup(markup)
        else:
            # Escape the content and add quotes
            from gi.repository import GLib

            escaped = GLib.markup_escape_text(text_content)
            markup = f"{open_quote}{escaped}{close_quote}"
            content_label.set_markup(markup)

        content_label.set_wrap(True)
        content_label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        content_label.set_ellipsize(Pango.EllipsizeMode.END)
        content_label.set_lines(3)
        content_label.set_halign(Gtk.Align.START)
        content_label.set_valign(Gtk.Align.START)
        content_label.add_css_class("clipboard-item-text")
        content_label.add_css_class("typewriter-text")
        content_label.set_selectable(False)
        content_label.set_xalign(0)
        content_label.set_yalign(0)
        content_label.set_hexpand(True)
        content_label.set_vexpand(False)
        content_label.set_max_width_chars(-1)

        container.append(content_label)
        return container

    def _build_file_content(self) -> Gtk.Widget:
        file_metadata = self.item.get("content", {})
        if not isinstance(file_metadata, dict):
            return self._build_error("Invalid file metadata")

        file_name = file_metadata.get("name", "Unknown file")
        file_size = file_metadata.get("size", 0)
        mime_type = file_metadata.get("mime_type", "application/octet-stream")
        extension = file_metadata.get("extension", "")
        is_directory = file_metadata.get("is_directory", False)

        file_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        file_box.set_halign(Gtk.Align.START)
        file_box.set_valign(Gtk.Align.CENTER)
        file_box.set_vexpand(False)
        file_box.set_margin_start(12)
        file_box.set_margin_top(12)
        file_box.set_margin_bottom(40)  # Space for tags overlay

        icon_name = get_file_icon(file_name, mime_type, is_directory)
        file_icon = Gtk.Image.new_from_icon_name(icon_name)
        file_icon.set_pixel_size(64)
        file_box.append(file_icon)

        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        info_box.set_halign(Gtk.Align.START)
        info_box.set_valign(Gtk.Align.CENTER)

        name_label = Gtk.Label()
        if self.search_query:
            highlighted = highlight_text(file_name, self.search_query)
            name_label.set_markup(highlighted)
        else:
            name_label.set_text(file_name)
        name_label.set_halign(Gtk.Align.START)
        name_label.add_css_class("title-4")
        name_label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        name_label.set_max_width_chars(50)
        info_box.append(name_label)

        if is_directory:
            meta_label = Gtk.Label(label="Folder")
        else:
            size_str = format_size(file_size)
            ext_display = extension.upper() if extension else mime_type
            meta_label = Gtk.Label(label=f"{size_str} • {ext_display}")
        meta_label.set_halign(Gtk.Align.START)
        meta_label.add_css_class("dim-label")
        meta_label.add_css_class("caption")
        info_box.append(meta_label)

        file_box.append(info_box)
        return file_box

    def _build_image_content(self) -> Gtk.Widget:
        try:
            thumbnail_data = self.item.get("thumbnail")
            image_data_b64 = (
                thumbnail_data if thumbnail_data else self.item["content"]
            )

            if not image_data_b64:
                raise Exception("No image data available")

            image_data = base64.b64decode(image_data_b64)
            loader = GdkPixbuf.PixbufLoader()
            loader.write(image_data)
            loader.close()
            pixbuf = loader.get_pixbuf()

            texture = Gdk.Texture.new_for_pixbuf(pixbuf)
            picture = Gtk.Picture.new_for_paintable(texture)
            picture.set_halign(Gtk.Align.CENTER)
            picture.set_valign(Gtk.Align.CENTER)
            picture.add_css_class("clipboard-item-image")
            picture.set_content_fit(Gtk.ContentFit.COVER)
            picture.set_hexpand(True)
            picture.set_vexpand(False)
            picture.set_can_shrink(True)
            picture.set_overflow(Gtk.Overflow.HIDDEN)

            # Wrap in container to add bottom margin for tags
            container = Gtk.Box()
            container.set_margin_bottom(40)  # Space for tags overlay
            container.append(picture)

            return container
        except Exception as e:
            return self._build_error(f"Failed to load image: {str(e)}")

    def _build_unknown_content(self) -> Gtk.Widget:
        label = Gtk.Label(label=f"Unknown content type: {self.item_type}")
        label.add_css_class("dim-label")
        return label

    def _build_error(self, message: str) -> Gtk.Widget:
        error_label = Gtk.Label(label=message)
        error_label.add_css_class("error")
        error_label.set_wrap(True)
        return error_label
