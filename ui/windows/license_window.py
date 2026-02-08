import gi
import os

gi.require_version('Gtk', '4.0')
from gi.repository import Gtk


class LicenseWindow(Gtk.Dialog):
    def __init__(self, parent=None, callback=None):
        super().__init__(title="License Agreement", modal=True, transient_for=parent)
        self.set_default_size(600, 500)
        self.license_accepted = False
        self.callback = callback

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        main_box.set_margin_top(10)
        main_box.set_margin_bottom(10)
        main_box.set_margin_start(10)
        main_box.set_margin_end(10)
        self.get_content_area().append(main_box)

        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_hexpand(True)
        scrolled_window.set_vexpand(True)
        main_box.append(scrolled_window)

        text_view = Gtk.TextView()
        text_view.set_editable(False)
        text_view.set_cursor_visible(False)
        text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        scrolled_window.set_child(text_view)

        buffer = text_view.get_buffer()
        buffer.set_text(self._load_license_text())

        # Add button with response
        self.add_button("Okay", Gtk.ResponseType.OK)
        self.set_default_response(Gtk.ResponseType.OK)

        # Connect to response signal
        self.connect("response", self._on_response)

    def _load_license_text(self):
        """Load license text from installed location or fallback to source."""
        # Try Flatpak installed location first
        license_paths = [
            "/app/share/licenses/tfcbm/LICENSE",  # Flatpak
            os.path.join(os.path.dirname(__file__), "..", "..", "LICENSE"),  # Development
        ]

        for path in license_paths:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return f.read()
            except FileNotFoundError:
                continue

        # Fallback if no license file found
        return "GPL-3.0-or-later\n\nLicense file not found. Please see https://www.gnu.org/licenses/gpl-3.0.html"

    def _on_response(self, dialog, response_id):
        if response_id == Gtk.ResponseType.OK:
            self.license_accepted = True
        # Call the callback before closing
        if self.callback:
            self.callback(self.license_accepted)
        self.destroy()