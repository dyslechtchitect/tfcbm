"""Item content display component."""

import base64

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, Gtk, Pango

from ui.components.items.item_formatting_indicator import FormattingIndicator
from ui.utils import format_size, get_file_icon, highlight_text


class ItemContent:
    def __init__(self, item: dict, search_query: str = ""):
        self.item = item
        self.search_query = search_query
        self.item_type = item.get("type", "unknown")

    def build(self) -> Gtk.Widget:
        content_clamp = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content_clamp.set_vexpand(True)  # LET CONTENT DETERMINE HEIGHT!
        content_clamp.set_hexpand(True)
        content_clamp.set_overflow(Gtk.Overflow.HIDDEN)

        # Check if item is secret - if so, show unified secret placeholder
        is_secret = self.item.get("is_secret", False)
        if is_secret:
            widget = self._build_secret_placeholder()
        elif self.item_type == "text" or self.item_type == "url":
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

    def _build_secret_placeholder(self) -> Gtk.Widget:
        """Build unified secret placeholder for all secret items."""
        container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        container.set_vexpand(True)
        container.set_hexpand(True)
        container.set_valign(Gtk.Align.CENTER)
        container.set_halign(Gtk.Align.CENTER)
        container.set_margin_top(40)
        container.set_margin_bottom(60)  # Space for tags overlay
        container.set_margin_start(20)
        container.set_margin_end(20)

        # Lock icon
        lock_icon = Gtk.Image.new_from_icon_name("changes-prevent-symbolic")
        lock_icon.set_pixel_size(48)
        lock_icon.add_css_class("error")  # Red color
        lock_icon.set_halign(Gtk.Align.CENTER)
        container.append(lock_icon)

        # "PROTECTED" label
        protected_label = Gtk.Label(label="PROTECTED")
        protected_label.add_css_class("title-2")
        protected_label.add_css_class("error")  # Red color
        protected_label.set_halign(Gtk.Align.CENTER)
        container.append(protected_label)

        # Subtle hint text
        hint_label = Gtk.Label(label="Authentication required to view")
        hint_label.add_css_class("dim-label")
        hint_label.add_css_class("caption")
        hint_label.set_halign(Gtk.Align.CENTER)
        container.append(hint_label)

        return container

    def _build_text_content(self) -> Gtk.Widget:
        container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        container.set_vexpand(True)  # LET TEXT WRAP AND DETERMINE HEIGHT!
        container.set_hexpand(True)
        container.set_overflow(Gtk.Overflow.HIDDEN)
        container.set_margin_bottom(40)  # Space for tags overlay

        # Add formatting indicator if present
        formatting_indicator = FormattingIndicator(self.item)
        indicator_widget = formatting_indicator.build()
        if indicator_widget:
            indicator_widget.set_margin_start(12)
            indicator_widget.set_margin_top(8)
            container.append(indicator_widget)

        text_content = self.item["content"]

        # If showing a page beyond page 0, prepend ellipsis to indicate prior content
        content_page = self.item.get("content_page", 0)
        if content_page > 0:
            text_content = "..." + text_content

        # Check if content was truncated and add indicator
        content_truncated = self.item.get("content_truncated", False)
        if content_truncated and not text_content.endswith("..."):
            text_content = text_content + "..."

        # Add quotes inline with the text content
        open_quote = (
            '<span font_family="serif" font_weight="heavy" '
            'size="28pt" alpha="60%">\u201c</span>'
        )
        close_quote = (
            '<span font_family="serif" font_weight="heavy" '
            'size="28pt" alpha="60%">\u201d</span>'
        )

        if self.search_query:
            # Use TextView for search results to enable scrolling to highlights
            content_widget = self._build_searchable_text_view(
                text_content, open_quote, close_quote
            )
        else:
            # Use Label for normal display
            content_label = Gtk.Label()
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
            content_widget = content_label

        container.append(content_widget)
        return container

    def _build_searchable_text_view(
        self, text_content: str, open_quote: str, close_quote: str
    ) -> Gtk.Widget:
        """Build a TextView with highlighted search terms and scroll to first match."""
        import re
        from gi.repository import GLib

        # Parse search query into terms (same logic as highlight_text)
        query = self.search_query.strip()
        if query.startswith('"') and query.endswith('"') and query.count('"') == 2:
            search_terms = [query[1:-1]]
        else:
            parts = re.findall(r'"[^"]+"|\S+', query)
            search_terms = [p.strip('"') for p in parts]

        # Create TextView
        text_view = Gtk.TextView()
        text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        text_view.set_editable(False)
        text_view.set_cursor_visible(False)
        text_view.set_hexpand(True)
        text_view.set_vexpand(False)
        text_view.add_css_class("clipboard-item-text")
        text_view.add_css_class("typewriter-text")

        # Get text buffer
        buffer = text_view.get_buffer()

        # Create highlight tag
        tag_table = buffer.get_tag_table()
        highlight_tag = Gtk.TextTag(name="highlight")
        highlight_tag.set_property("background", "yellow")
        highlight_tag.set_property("foreground", "black")
        tag_table.add(highlight_tag)

        # Insert opening quote with markup (need to handle manually)
        # Actually, TextBuffer doesn't support markup directly, so we'll skip the fancy quotes
        # and just show the text with highlights

        # Insert text
        buffer.set_text(text_content)

        # Find and highlight all matches, and remember first match position
        first_match_iter = None
        for term in search_terms:
            if not term:
                continue

            # Search for all occurrences of this term (case-insensitive)
            start_iter = buffer.get_start_iter()
            while True:
                match = start_iter.forward_search(
                    term,
                    Gtk.TextSearchFlags.CASE_INSENSITIVE,
                    None,
                )
                if not match:
                    break

                match_start, match_end = match
                if first_match_iter is None:
                    first_match_iter = match_start.copy()

                buffer.apply_tag(highlight_tag, match_start, match_end)
                start_iter = match_end

        # Wrap in ScrolledWindow with fixed height (3 lines worth)
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_child(text_view)
        scrolled.set_max_content_height(100)  # Roughly 3 lines
        scrolled.set_propagate_natural_height(True)

        # Scroll to first match after widget is realized
        if first_match_iter:

            def scroll_to_match():
                text_view.scroll_to_iter(first_match_iter, 0.0, True, 0.0, 0.0)
                return False

            # Use idle_add to scroll after widget is fully laid out
            from gi.repository import GLib

            GLib.idle_add(scroll_to_match)

        return scrolled

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
            picture.set_valign(Gtk.Align.FILL)
            picture.add_css_class("clipboard-item-image")
            picture.set_content_fit(Gtk.ContentFit.SCALE_DOWN)  # Scale down to fit, never exceed bounds
            picture.set_hexpand(True)
            picture.set_vexpand(True)  # Expand to fill height
            picture.set_can_shrink(True)
            picture.set_overflow(Gtk.Overflow.HIDDEN)

            # No container wrapper - return picture directly (no bottom margin for images)
            return picture
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
