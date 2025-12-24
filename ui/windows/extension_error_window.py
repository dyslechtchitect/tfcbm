"""Extension Setup Window - shown when GNOME extension is not ready."""

import logging
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GdkPixbuf", "2.0")

from gi.repository import Adw, Gdk, GdkPixbuf, GLib, Gtk

logger = logging.getLogger("TFCBM.UI")


class ExtensionErrorWindow(Adw.ApplicationWindow):
    """Setup window for GNOME extension installation or enabling."""

    def __init__(self, app, extension_status: dict):
        super().__init__(application=app, title="TFCBM - Extension Setup")

        self.extension_status = extension_status
        self.set_default_size(700, 600)
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
        if not extension_status['installed']:
            title_text = "GNOME Extension Required"
        else:
            title_text = "Please Enable GNOME Extension"
        title_label.set_markup(f"<span size='xx-large' weight='bold'>{title_text}</span>")
        title_label.set_halign(Gtk.Align.CENTER)
        main_box.append(title_label)

        # Description
        desc_label = Gtk.Label()
        if not extension_status['installed']:
            desc_text = (
                "TFCBM needs its GNOME extension to monitor your clipboard.\n"
                "The extension is bundled with TFCBM and ready to install."
            )
        else:
            desc_text = (
                "The TFCBM extension is installed but not enabled.\n"
                "Please enable it to start using TFCBM."
            )
        desc_label.set_markup(desc_text)
        desc_label.set_halign(Gtk.Align.CENTER)
        desc_label.set_wrap(True)
        desc_label.set_justify(Gtk.Justification.CENTER)
        main_box.append(desc_label)

        # Instructions box
        instructions_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        instructions_box.set_margin_top(12)

        if not extension_status['installed']:
            # Show installation options
            self._add_installation_section(instructions_box)
        else:
            # Show enable options
            self._add_enable_section(instructions_box)

        main_box.append(instructions_box)

        # Status label (for feedback)
        self.status_label = Gtk.Label()
        self.status_label.set_wrap(True)
        self.status_label.set_halign(Gtk.Align.CENTER)
        self.status_label.set_visible(False)
        main_box.append(self.status_label)

        # Button box
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        button_box.set_halign(Gtk.Align.CENTER)
        button_box.set_margin_top(24)

        if not extension_status['installed']:
            # Install button
            install_button = Gtk.Button(label="Install Extension")
            install_button.add_css_class("suggested-action")
            install_button.connect("clicked", self._on_install_clicked)
            button_box.append(install_button)
        else:
            # Enable button
            enable_button = Gtk.Button(label="Enable Extension")
            enable_button.add_css_class("suggested-action")
            enable_button.connect("clicked", self._on_enable_clicked)
            button_box.append(enable_button)

        # Check Again button
        retry_button = Gtk.Button(label="Check Again")
        retry_button.connect("clicked", self._on_retry_clicked)
        button_box.append(retry_button)

        # Close button
        close_button = Gtk.Button(label="Close")
        close_button.connect("clicked", lambda btn: self.close())
        button_box.append(close_button)

        main_box.append(button_box)

        self.set_content(main_box)

    def _add_installation_section(self, container):
        """Add installation instructions and command."""
        section_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        section_title = Gtk.Label()
        section_title.set_markup("<b>Option 1: Click the Install button above</b>")
        section_title.set_halign(Gtk.Align.START)
        section_box.append(section_title)

        or_label = Gtk.Label()
        or_label.set_markup("<b>Option 2: Use command line:</b>")
        or_label.set_halign(Gtk.Align.START)
        or_label.set_margin_top(12)
        section_box.append(or_label)

        # Command display with copy button
        from ui.utils.extension_check import get_extension_install_command
        command = get_extension_install_command()
        self._add_command_box(section_box, command)

        # Note about logout
        note_label = Gtk.Label()
        note_label.set_markup(
            "<span size='small' alpha='60%'>"
            "Note: You may need to log out and log back in after installation."
            "</span>"
        )
        note_label.set_halign(Gtk.Align.START)
        note_label.set_wrap(True)
        note_label.set_margin_top(12)
        section_box.append(note_label)

        container.append(section_box)

    def _add_enable_section(self, container):
        """Add enable instructions and command."""
        section_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        section_title = Gtk.Label()
        section_title.set_markup("<b>Option 1: Click the Enable button above</b>")
        section_title.set_halign(Gtk.Align.START)
        section_box.append(section_title)

        or_label = Gtk.Label()
        or_label.set_markup("<b>Option 2: Use command line:</b>")
        or_label.set_halign(Gtk.Align.START)
        or_label.set_margin_top(12)
        section_box.append(or_label)

        # Command display with copy button
        from ui.utils.extension_check import get_extension_enable_command
        command = get_extension_enable_command()
        self._add_command_box(section_box, command)

        container.append(section_box)

    def _add_command_box(self, container, command):
        """Add a command display box with copy button."""
        cmd_container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

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

            GLib.timeout_add(2000, reset_icon)

        copy_button.connect("clicked", on_copy_clicked)
        cmd_container.append(copy_button)

        container.append(cmd_container)

    def _on_install_clicked(self, button):
        """Handle install button click."""
        button.set_sensitive(False)
        button.set_label("Installing...")

        from ui.utils.extension_check import install_extension

        def install_in_thread():
            success, message = install_extension()

            def update_ui():
                button.set_sensitive(True)
                button.set_label("Install Extension")

                self.status_label.set_visible(True)
                if success:
                    self.status_label.set_markup(
                        f"<span color='green'>{message}</span>\n"
                        "<span size='small'>Please log out and log back in, then click 'Check Again'</span>"
                    )
                else:
                    self.status_label.set_markup(f"<span color='red'>Error: {message}</span>")

                return False

            GLib.idle_add(update_ui)

        # Run in background to avoid blocking UI
        import threading
        threading.Thread(target=install_in_thread, daemon=True).start()

    def _on_enable_clicked(self, button):
        """Handle enable button click."""
        button.set_sensitive(False)
        button.set_label("Enabling...")

        from ui.utils.extension_check import enable_extension

        def enable_in_thread():
            success, message = enable_extension()

            def update_ui():
                button.set_sensitive(True)
                button.set_label("Enable Extension")

                self.status_label.set_visible(True)
                if success:
                    self.status_label.set_markup(
                        f"<span color='green'>{message}</span>\n"
                        "<span size='small'>Click 'Check Again' to continue</span>"
                    )
                    # Auto-retry after 2 seconds
                    GLib.timeout_add(2000, lambda: self._on_retry_clicked(None))
                else:
                    self.status_label.set_markup(f"<span color='red'>Error: {message}</span>")

                return False

            GLib.idle_add(update_ui)

        # Run in background
        import threading
        threading.Thread(target=enable_in_thread, daemon=True).start()

    def _on_retry_clicked(self, button):
        """Handle retry button click - check if extension is now ready."""
        from ui.utils.extension_check import get_extension_status

        status = get_extension_status()

        if status['ready']:
            logger.info("Extension is now ready! Closing setup window...")
            # Close this window and let the app continue loading
            self.close()
            # Trigger the app to continue initialization
            self.get_application().emit("activate")
        else:
            # Update the window to reflect current status
            if not status['installed']:
                message = "Extension is still not installed. Please install it first."
            elif not status['enabled']:
                message = "Extension is installed but not enabled. Please enable it."
            else:
                message = "Extension status unclear. Please try again."

            # Show notification
            toast = Adw.Toast.new(message)
            toast.set_timeout(3)

            # Create an overlay if we don't have one
            content = self.get_content()
            if not isinstance(content, Adw.ToastOverlay):
                overlay = Adw.ToastOverlay()
                overlay.set_child(content)
                self.set_content(overlay)
                overlay.add_toast(toast)
            else:
                content.add_toast(toast)
