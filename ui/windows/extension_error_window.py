"""Extension Setup Window - shown when GNOME extension is not ready."""

import logging
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GdkPixbuf", "2.0")

from gi.repository import Adw, Gdk, GdkPixbuf, Gio, GLib, Gtk

logger = logging.getLogger("TFCBM.UI")


class ExtensionErrorWindow(Adw.ApplicationWindow):
    """Setup window for GNOME extension installation or enabling."""

    def __init__(self, app, extension_status: dict):
        super().__init__(application=app, title="TFCBM - Extension Setup")

        self.extension_status = extension_status
        self.install_succeeded = False  # Track if install button succeeded
        self.set_default_size(700, 600)
        self.set_resizable(False)
        self.set_deletable(True)  # Ensure window has X button

        # Connect to close request to show restart dialog if needed
        self.connect("close-request", self._on_close_request)

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
            # Try Flatpak path first, then development path
            icon_paths = [
                Path("/app/share/icons/hicolor/scalable/apps/org.tfcbm.ClipboardManager.svg"),
                Path(__file__).parent.parent.parent / "icons" / "hicolor" / "scalable" / "apps" / "org.tfcbm.ClipboardManager.svg"
            ]

            for icon_path in icon_paths:
                if icon_path.exists():
                    texture = Gdk.Texture.new_from_file(Gio.File.new_for_path(str(icon_path)))
                    icon_picture = Gtk.Picture.new_for_paintable(texture)
                    icon_picture.set_size_request(128, 128)
                    icon_picture.set_halign(Gtk.Align.CENTER)
                    main_box.append(icon_picture)
                    break
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

        # Simple instruction - just click the button
        section_title = Gtk.Label()
        section_title.set_markup("<b>Click the 'Install Extension' button above to continue</b>")
        section_title.set_halign(Gtk.Align.START)
        section_box.append(section_title)

        info_label = Gtk.Label()
        info_label.set_markup(
            "The GNOME extension is bundled with TFCBM and will be\n"
            "installed automatically when you click the button."
        )
        info_label.set_halign(Gtk.Align.START)
        info_label.set_wrap(True)
        info_label.set_margin_top(8)
        section_box.append(info_label)

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

    def _add_command_box(self, container, command, on_copy_callback=None):
        """Add a command display box with copy button.

        Args:
            container: The parent container to add to
            command: The command string to display
            on_copy_callback: Optional callback to run when copy button is clicked
        """
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

            # Call the callback if provided
            if on_copy_callback:
                on_copy_callback()

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

                if success:
                    # Extension installed successfully
                    self.install_succeeded = True
                    self.status_label.set_visible(True)

                    # Show restart instructions
                    import os
                    session_type = os.environ.get('XDG_SESSION_TYPE', 'unknown')

                    if session_type == 'x11':
                        restart_msg = (
                            "<span color='green'>✓ Extension installed!</span>\n\n"
                            "<b>Next steps:</b>\n"
                            "1. Press Alt+F2\n"
                            "2. Type: <tt>r</tt>\n"
                            "3. Press Enter to restart GNOME Shell\n"
                            "4. Launch TFCBM again"
                        )
                    else:  # Wayland or unknown
                        restart_msg = (
                            "<span color='green'>✓ Extension installed!</span>\n\n"
                            "<b>Next steps:</b>\n"
                            "1. Log out\n"
                            "2. Log back in\n"
                            "3. Launch TFCBM again"
                        )

                    self.status_label.set_markup(restart_msg)
                else:
                    self.status_label.set_visible(True)
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
                if success:
                    # Extension enabled successfully - close window and launch app
                    logger.info("Extension enabled successfully, launching main app")
                    # Get app reference before closing window
                    app = self.get_application()
                    self.close()
                    # Directly trigger loading the main window
                    if app:
                        GLib.idle_add(lambda: (app._show_splash(), app._load_main_window()))
                else:
                    # Show error message
                    button.set_sensitive(True)
                    button.set_label("Enable Extension")
                    self.status_label.set_visible(True)
                    self.status_label.set_markup(f"<span color='red'>Error: {message}</span>")

                return False

            GLib.idle_add(update_ui)

        # Run in background
        import threading
        threading.Thread(target=enable_in_thread, daemon=True).start()

    def _on_retry_clicked(self, button):
        """Handle retry button click - check if extension is now ready."""
        if button:  # Button might be None when auto-triggered
            button.set_sensitive(False)
            button.set_label("Checking...")

        from ui.utils.extension_check import get_extension_status

        status = get_extension_status()

        if button:
            button.set_sensitive(True)
            button.set_label("Check Again")

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

            # Show message in status label instead of recreating window
            self.status_label.set_visible(True)
            self.status_label.set_markup(f"<span color='orange'>{message}</span>")

    def _on_close_request(self, window):
        """Handle window close."""
        # If extension was just installed, user needs to restart GNOME Shell first
        # So quit the app and let them relaunch after restart
        app = self.get_application()
        if app:
            app.quit()
        return False
