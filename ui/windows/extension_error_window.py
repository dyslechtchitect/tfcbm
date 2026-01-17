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
        self.launching_app = False  # Track if we're closing to launch the app
        self.set_default_size(900, 600)
        self.set_resizable(True)
        self.set_deletable(True)  # Ensure window has X button

        # Connect to close request to show restart dialog if needed
        self.connect("close-request", self._on_close_request)

        # Main container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        main_box.set_margin_start(24)
        main_box.set_margin_end(24)
        main_box.set_margin_top(24)
        main_box.set_margin_bottom(24)

        # Icon - smaller
        try:
            # Try Flatpak path first, then development path
            icon_paths = [
                Path("/app/share/icons/hicolor/scalable/apps/io.github.dyslechtchitect.tfcbm.svg"),
                Path(__file__).parent.parent.parent / "icons" / "hicolor" / "scalable" / "apps" / "io.github.dyslechtchitect.tfcbm.svg"
            ]

            for icon_path in icon_paths:
                if icon_path.exists():
                    texture = Gdk.Texture.new_from_file(Gio.File.new_for_path(str(icon_path)))
                    icon_picture = Gtk.Picture.new_for_paintable(texture)
                    icon_picture.set_size_request(64, 64)
                    icon_picture.set_halign(Gtk.Align.CENTER)
                    main_box.append(icon_picture)
                    break
        except Exception as e:
            logger.warning(f"Could not load icon: {e}")

        # Title - smaller
        title_label = Gtk.Label()
        if not extension_status['installed']:
            title_text = "GNOME Extension Required"
        elif extension_status.get('needs_enable', False):
            title_text = "One More Step"
        else:
            title_text = "Enable GNOME Extension"
        title_label.set_markup(f"<span size='large' weight='bold'>{title_text}</span>")
        title_label.set_halign(Gtk.Align.CENTER)
        main_box.append(title_label)

        # Description - more compact
        desc_label = Gtk.Label()
        if not extension_status['installed']:
            desc_text = "TFCBM needs its GNOME extension to monitor your clipboard."
        elif extension_status.get('needs_enable', False):
            desc_text = "Just enable the extension and you're good to go!"
        else:
            desc_text = "The extension is installed but not enabled."
        desc_label.set_markup(f"<span size='small'>{desc_text}</span>")
        desc_label.set_halign(Gtk.Align.CENTER)
        desc_label.set_wrap(True)
        desc_label.set_justify(Gtk.Justification.CENTER)
        main_box.append(desc_label)

        # Instructions box
        instructions_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

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

        # Button box (only Check and Launch and Close buttons)
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        button_box.set_halign(Gtk.Align.CENTER)
        button_box.set_margin_top(12)

        # Check and Launch button
        retry_button = Gtk.Button(label="Check and Launch")
        retry_button.add_css_class("suggested-action")
        retry_button.connect("clicked", self._on_retry_clicked)
        button_box.append(retry_button)

        # Close button
        close_button = Gtk.Button(label="Close")
        close_button.connect("clicked", lambda btn: self.close())
        button_box.append(close_button)

        main_box.append(button_box)

        self.set_content(main_box)

        # Auto-check on window open - if extension is ready, launch immediately
        GLib.timeout_add(500, self._auto_check_and_launch)

    def _add_installation_section(self, container):
        """Add installation instructions with commands."""
        section_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        # Step 1: Install
        step1_label = Gtk.Label()
        step1_label.set_markup("<b>Step 1: Install</b>")
        step1_label.set_halign(Gtk.Align.START)
        section_box.append(step1_label)

        # Install command - different for Flatpak vs native
        from ui.utils.extension_check import is_flatpak
        if is_flatpak():
            # For Flatpak: copy from Flatpak's bundled location to user's home
            # Try user install first, fall back to system if needed
            install_cmd = (
                "mkdir -p ~/.local/share/gnome-shell/extensions/tfcbm-clipboard-monitor@github.com && \\\n"
                "cp -r ~/.local/share/flatpak/app/io.github.dyslechtchitect.tfcbm/current/active/files/share/gnome-shell/extensions/tfcbm-clipboard-monitor@github.com/* \\\n"
                "~/.local/share/gnome-shell/extensions/tfcbm-clipboard-monitor@github.com/ 2>/dev/null || \\\n"
                "cp -r /var/lib/flatpak/app/io.github.dyslechtchitect.tfcbm/current/active/files/share/gnome-shell/extensions/tfcbm-clipboard-monitor@github.com/* \\\n"
                "~/.local/share/gnome-shell/extensions/tfcbm-clipboard-monitor@github.com/ && \\\n"
                "glib-compile-schemas ~/.local/share/gnome-shell/extensions/tfcbm-clipboard-monitor@github.com/schemas/"
            )

            self._add_command_box(section_box, install_cmd, multiline=True)
        else:
            install_cmd = "tfcbm-install-extension"
            self._add_command_box(section_box, install_cmd)

        # Step 2: Logout and Login
        step2_label = Gtk.Label()
        step2_label.set_markup("<b>Step 2: Log out and back in</b>")
        step2_label.set_halign(Gtk.Align.START)
        step2_label.set_margin_top(8)
        section_box.append(step2_label)

        # Step 3: Enable
        step3_label = Gtk.Label()
        step3_label.set_markup("<b>Step 3: Enable</b>")
        step3_label.set_halign(Gtk.Align.START)
        step3_label.set_margin_top(8)
        section_box.append(step3_label)

        # Enable command
        enable_cmd = "gnome-extensions enable tfcbm-clipboard-monitor@github.com"
        self._add_command_box(section_box, enable_cmd)

        # Final note
        final_note = Gtk.Label()
        final_note.set_markup("<span size='small'>Then click <b>'Check and Launch'</b> below.</span>")
        final_note.set_halign(Gtk.Align.START)
        final_note.set_margin_top(8)
        section_box.append(final_note)

        container.append(section_box)

    def _add_enable_section(self, container):
        """Add enable instructions with command."""
        section_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        # Check if we need to show the "log out" step
        # If needs_enable is True, it means files are installed but extension not enabled yet
        needs_logout = self.extension_status.get('needs_enable', False)

        if needs_logout:
            # User has already logged out and back in, just needs to enable
            step_label = Gtk.Label()
            step_label.set_markup("<b>Enable the extension:</b>")
            step_label.set_halign(Gtk.Align.START)
            section_box.append(step_label)

            # Enable command
            enable_cmd = "gnome-extensions enable tfcbm-clipboard-monitor@github.com"
            self._add_command_box(section_box, enable_cmd)

            # Final note
            final_note = Gtk.Label()
            final_note.set_markup("<span size='small'>Then click <b>'Check and Launch'</b> below.</span>")
            final_note.set_halign(Gtk.Align.START)
            final_note.set_margin_top(8)
            section_box.append(final_note)
        else:
            # Original flow for first-time enable (before reboot)
            # Step 1: Enable
            step1_label = Gtk.Label()
            step1_label.set_markup("<b>Step 1: Enable</b>")
            step1_label.set_halign(Gtk.Align.START)
            section_box.append(step1_label)

            # Enable command
            enable_cmd = "gnome-extensions enable tfcbm-clipboard-monitor@github.com"
            self._add_command_box(section_box, enable_cmd)

            # Step 2: Logout and Login
            step2_label = Gtk.Label()
            step2_label.set_markup("<b>Step 2: Log out and back in</b>")
            step2_label.set_halign(Gtk.Align.START)
            step2_label.set_margin_top(8)
            section_box.append(step2_label)

            # Final note
            final_note = Gtk.Label()
            final_note.set_markup("<span size='small'>Then click <b>'Check and Launch'</b> below.</span>")
            final_note.set_halign(Gtk.Align.START)
            final_note.set_margin_top(8)
            section_box.append(final_note)

        container.append(section_box)

    def _add_command_box(self, container, command, on_copy_callback=None, multiline=False):
        """Add a command display box with copy button.

        Args:
            container: The parent container to add to
            command: The command string to display
            on_copy_callback: Optional callback to run when copy button is clicked
            multiline: Whether to use a TextView for multiline commands
        """
        cmd_container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        cmd_container.set_valign(Gtk.Align.START)

        if multiline:
            # Use TextView for multiline commands with terminal-like styling
            frame = Gtk.Frame()
            frame.set_hexpand(True)

            text_view = Gtk.TextView()
            text_view.set_editable(False)
            text_view.set_cursor_visible(False)
            text_view.set_wrap_mode(Gtk.WrapMode.NONE)
            text_view.set_monospace(True)
            text_view.set_left_margin(10)
            text_view.set_right_margin(10)
            text_view.set_top_margin(10)
            text_view.set_bottom_margin(10)

            # Create CSS provider for terminal-like styling
            css_provider = Gtk.CssProvider()
            css_provider.load_from_data(b"""
                textview {
                    background-color: #1e1e1e;
                    color: #00ff00;
                    font-size: 9pt;
                    font-family: monospace;
                }
                textview text {
                    background-color: #1e1e1e;
                    color: #00ff00;
                }
            """)

            text_view.get_style_context().add_provider(
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

            # Add prompt to the command
            terminal_text = f"$ {command}"
            text_buffer = text_view.get_buffer()
            text_buffer.set_text(terminal_text)

            frame.set_child(text_view)
            cmd_container.append(frame)
        else:
            # Use Entry for single-line commands with terminal styling
            cmd_entry = Gtk.Entry()
            cmd_entry.set_text(f"$ {command}")
            cmd_entry.set_editable(False)
            cmd_entry.set_hexpand(True)

            # Create CSS provider for terminal-like styling
            css_provider = Gtk.CssProvider()
            css_provider.load_from_data(b"""
                entry {
                    background-color: #1e1e1e;
                    color: #00ff00;
                    font-size: 9pt;
                    font-family: monospace;
                    padding: 8px;
                }
                entry text {
                    background-color: #1e1e1e;
                    color: #00ff00;
                }
            """)

            cmd_entry.get_style_context().add_provider(
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

            cmd_container.append(cmd_entry)

        copy_button = Gtk.Button()
        copy_button.set_icon_name("edit-copy-symbolic")
        copy_button.set_tooltip_text("Copy command")
        copy_button.set_valign(Gtk.Align.START)

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
                    logger.info("Extension installed successfully, checking if ready to proceed")

                    # Check if extension is now ready (our new logic accepts INITIALIZED+Enabled)
                    from ui.utils.extension_check import get_extension_status
                    import time
                    time.sleep(0.5)  # Give GNOME Shell a moment to update

                    status = get_extension_status()
                    if status['ready']:
                        # Extension is ready! - close window and launch app
                        logger.info("Extension is ready after installation, launching main app")
                        app = self.get_application()
                        self.close()
                        if app:
                            GLib.idle_add(lambda: (app._show_splash(), app._load_main_window()))
                    else:
                        # Extension installed but not ready - show restart instructions
                        self.install_succeeded = True
                        self.status_label.set_visible(True)

                        restart_msg = (
                            "<span color='green'>✓ Extension installed!</span>\n\n"
                            "<b>Next steps:</b>\n"
                            "1. Log out\n"
                            "2. Log back in\n"
                            "3. Enable the extension (see Step 3 above)\n"
                            "4. Click 'Check and Launch' button"
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
        """Handle enable button click - show instructions for manual enable."""
        button.set_sensitive(False)
        self.status_label.set_visible(True)

        import os
        session_type = os.environ.get('XDG_SESSION_TYPE', 'unknown')

        instructions_msg = (
            "<b>To enable the extension, run this command in your terminal:</b>\n\n"
            "<tt>gnome-extensions enable tfcbm-clipboard-monitor@github.com</tt>\n\n"
        )

        if session_type == 'x11':
            instructions_msg += (
                "<b>Then restart GNOME Shell:</b>\n"
                "1. Press Alt+F2\n"
                "2. Type: <tt>r</tt>\n"
                "3. Press Enter\n"
                "4. Click 'Check and Launch' button below"
            )
        else:
            instructions_msg += (
                "<b>Then log out and back in, and click 'Check and Launch' button below</b>"
            )

        self.status_label.set_markup(instructions_msg)

    def _on_retry_clicked(self, button):
        """Handle retry button click - check if extension is now ready."""
        if button:  # Button might be None when auto-triggered
            button.set_sensitive(False)
            button.set_label("Checking...")

        from ui.utils.extension_check import get_extension_status

        status = get_extension_status()

        if button:
            button.set_sensitive(True)
            button.set_label("Check and Launch")

        if status['ready']:
            logger.info("Extension is now ready! Opening main app...")

            # Get the application instance
            app = self.get_application()
            if not app:
                logger.error("Failed to get application instance")
                self.status_label.set_visible(True)
                self.status_label.set_markup("<span color='red'>Error: Application not found</span>")
                return

            # Mark that we're launching the app (don't quit on close)
            self.launching_app = True

            # Hold the app to prevent it from quitting when we close this window
            logger.info("DEBUG: Calling app.hold() to prevent auto-quit")
            app.hold()

            # Close this window first
            self.close()

            # Show splash and load main window, skipping extension check since we just verified it
            logger.info("Launching main app with splash and main window...")

            def launch_app():
                logger.info("DEBUG: launch_app called, showing splash")
                app._show_splash()

                def load_window():
                    logger.info("DEBUG: load_window called, calling _load_main_window with skip_extension_check=True")
                    app._load_main_window(skip_extension_check=True)
                    # Release the hold after main window is created
                    app.release()
                    return False

                GLib.timeout_add(100, load_window)
                return False

            GLib.idle_add(launch_app)

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

    def _auto_check_and_launch(self):
        """Auto-check if extension is ready and launch if so."""
        from ui.utils.extension_check import get_extension_status

        status = get_extension_status()

        if status['ready']:
            logger.info("Extension is ready on window open - auto-launching main app")
            # Call the same logic as the retry button
            self._on_retry_clicked(None)

        return False  # Don't repeat

    def _on_close_request(self, window):
        """Handle window close."""
        # If we're closing to launch the app, don't quit
        if self.launching_app:
            logger.info("Closing extension error window to launch app (not quitting)")
            return False

        # Otherwise, user is closing the window manually, so quit the app
        logger.info("Extension error window closed by user, quitting app")
        app = self.get_application()
        if app:
            app.quit()
        return False
