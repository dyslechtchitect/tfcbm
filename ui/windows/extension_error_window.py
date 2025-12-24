"""Extension Error Window - shown when GNOME extension is not installed."""

import logging
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GdkPixbuf", "2.0")

from gi.repository import Adw, Gdk, GdkPixbuf, Gtk

logger = logging.getLogger("TFCBM.UI")


class ExtensionErrorWindow(Adw.ApplicationWindow):
    """Error window displayed when GNOME extension is not installed."""

    def __init__(self, app):
        super().__init__(application=app, title="TFCBM - Extension Required")

        self.set_default_size(600, 500)
        self.set_resizable(False)

        # Main container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        main_box.set_margin_start(48)
        main_box.set_margin_end(48)
        main_box.set_margin_top(48)
        main_box.set_margin_bottom(48)
        main_box.set_valign(Gtk.Align.CENTER)
        main_box.set_halign(Gtk.Align.CENTER)

        # Icon
        try:
            icon_path = Path(__file__).parent.parent.parent / "resouces" / "icon.svg"
            if icon_path.exists():
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    str(icon_path), 128, 128, True
                )
                texture = Gdk.Texture.new_for_pixbuf(pixbuf)
                icon_picture = Gtk.Picture.new_for_paintable(texture)
                icon_picture.set_halign(Gtk.Align.CENTER)
                main_box.append(icon_picture)
        except Exception as e:
            logger.warning(f"Could not load icon: {e}")

        # Title
        title_label = Gtk.Label()
        title_label.set_markup("<span size='xx-large' weight='bold'>GNOME Extension Required</span>")
        title_label.set_halign(Gtk.Align.CENTER)
        main_box.append(title_label)

        # Description
        desc_label = Gtk.Label()
        desc_label.set_markup(
            "TFCBM needs its GNOME extension to work.\n"
            "The extension monitors your clipboard and sends events to TFCBM."
        )
        desc_label.set_halign(Gtk.Align.CENTER)
        desc_label.set_wrap(True)
        desc_label.set_justify(Gtk.Justification.CENTER)
        main_box.append(desc_label)

        # Instructions box
        instructions_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        instructions_box.set_margin_top(12)

        # Option 1: Command line
        cmd_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        cmd_title = Gtk.Label()
        cmd_title.set_markup("<b>Install via command line:</b>")
        cmd_title.set_halign(Gtk.Align.START)
        cmd_box.append(cmd_title)

        # Command display with copy button
        cmd_container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        command = "gnome-extensions install tfcbm-clipboard-monitor@github.com.shell-extension.zip"
        cmd_entry = Gtk.Entry()
        cmd_entry.set_text(command)
        cmd_entry.set_editable(False)
        cmd_entry.set_hexpand(True)
        cmd_entry.add_css_class("monospace")
        cmd_container.append(cmd_entry)

        copy_button = Gtk.Button()
        copy_button.set_icon_name("edit-copy-symbolic")
        copy_button.set_tooltip_text("Copy command")

        def on_copy_clicked(btn):
            clipboard = Gdk.Display.get_default().get_clipboard()
            clipboard.set(command)
            btn.set_icon_name("object-select-symbolic")

            def reset_icon():
                btn.set_icon_name("edit-copy-symbolic")
                return False

            from gi.repository import GLib
            GLib.timeout_add(2000, reset_icon)

        copy_button.connect("clicked", on_copy_clicked)
        cmd_container.append(copy_button)

        cmd_box.append(cmd_container)
        instructions_box.append(cmd_box)

        # Note
        note_label = Gtk.Label()
        note_label.set_markup(
            "<span size='small' alpha='60%'>"
            "Note: You may need to log out and log back in after installing the extension."
            "</span>"
        )
        note_label.set_halign(Gtk.Align.START)
        note_label.set_wrap(True)
        instructions_box.append(note_label)

        main_box.append(instructions_box)

        # Button box
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        button_box.set_halign(Gtk.Align.CENTER)
        button_box.set_margin_top(24)

        # Retry button
        retry_button = Gtk.Button(label="Check Again")
        retry_button.add_css_class("suggested-action")
        retry_button.connect("clicked", self._on_retry_clicked)
        button_box.append(retry_button)

        # Close button
        close_button = Gtk.Button(label="Close")
        close_button.connect("clicked", lambda btn: self.close())
        button_box.append(close_button)

        main_box.append(button_box)

        self.set_content(main_box)

    def _on_retry_clicked(self, button):
        """Handle retry button click - check if extension is now installed."""
        from ui.utils.extension_check import is_extension_installed

        if is_extension_installed():
            logger.info("Extension now installed! Closing error window...")
            # Close this window and let the app continue loading
            self.close()
            # Trigger the app to continue initialization
            self.get_application().emit("activate")
        else:
            # Show notification that extension is still not found
            toast = Adw.Toast.new("Extension not found. Please install it first.")
            toast.set_timeout(3)

            # Create an overlay if we don't have one
            overlay = Adw.ToastOverlay()
            overlay.set_child(self.get_content())
            overlay.add_toast(toast)
            self.set_content(overlay)
