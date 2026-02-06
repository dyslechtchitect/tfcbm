"""GTK4 password dialog for secrets authentication.

Provides a DE-agnostic password dialog that collects the user's system
password. Replaces the pkexec polkit agent dialog so it works on any DE.
"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")

from gi.repository import Gdk, GLib, Gtk


class PasswordDialog:
    """Native GTK4 password dialog with synchronous run() API.

    Uses a nested GLib.MainLoop so callers can treat it as blocking
    while the UI stays responsive.
    """

    def __init__(self, parent_window, verify_fn=None):
        """Initialize the password dialog.

        Args:
            parent_window: Parent window for modality
            verify_fn: callable(password) -> bool for verification
        """
        self.verify_fn = verify_fn
        self._result = None  # None = cancelled, str = password
        self._loop = GLib.MainLoop()

        self.dialog = Gtk.Window(modal=True)
        if parent_window:
            self.dialog.set_transient_for(parent_window)
        self.dialog.set_default_size(380, -1)
        self.dialog.set_resizable(False)
        self.dialog.set_title("Authentication Required")

        # Quit loop on any close (X button, Escape, or programmatic close)
        self.dialog.connect("close-request", self._on_close_request)

        # Close on Escape
        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.connect("key-pressed", self._on_key_pressed)
        self.dialog.add_controller(key_ctrl)

        # --- Layout ---
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        main_box.set_margin_start(24)
        main_box.set_margin_end(24)
        main_box.set_margin_top(20)
        main_box.set_margin_bottom(20)

        # Lock icon
        lock_icon = Gtk.Image.new_from_icon_name("changes-prevent-symbolic")
        lock_icon.set_pixel_size(48)
        lock_icon.add_css_class("error")
        main_box.append(lock_icon)

        title = Gtk.Label(label="Authentication Required")
        title.add_css_class("title-3")
        main_box.append(title)

        desc = Gtk.Label(label="Enter your password to access this secret.")
        desc.set_wrap(True)
        desc.set_justify(Gtk.Justification.CENTER)
        desc.add_css_class("dim-label")
        main_box.append(desc)

        self.password_entry = Gtk.PasswordEntry(
            show_peek_icon=True, placeholder_text="Password"
        )
        self.password_entry.connect("activate", lambda _: self._on_submit())
        main_box.append(self.password_entry)

        # Error label (hidden until needed)
        self.error_label = Gtk.Label()
        self.error_label.add_css_class("error")
        self.error_label.set_visible(False)
        main_box.append(self.error_label)

        # Buttons
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        btn_box.set_halign(Gtk.Align.END)
        btn_box.set_margin_top(4)

        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda _: self._on_cancel())
        btn_box.append(cancel_btn)

        submit_btn = Gtk.Button(label="Unlock")
        submit_btn.add_css_class("suggested-action")
        submit_btn.connect("clicked", lambda _: self._on_submit())
        btn_box.append(submit_btn)

        main_box.append(btn_box)
        self.dialog.set_child(main_box)

        # Focus password entry on map
        self.dialog.connect("map", lambda _: self.password_entry.grab_focus())

    # --- Public API ---

    def run(self):
        """Show the dialog and block until the user responds.

        Returns:
            The password string on success, or None if cancelled.
        """
        self.dialog.present()
        self._loop.run()
        return self._result

    # --- Internal ---

    def _on_close_request(self, _window):
        """Handle any window close — quit the nested loop."""
        if self._loop.is_running():
            self._loop.quit()
        return False  # allow the close to proceed

    def _on_key_pressed(self, _ctrl, keyval, _keycode, _state):
        if keyval == Gdk.KEY_Escape:
            self._on_cancel()
            return True
        return False

    def _on_cancel(self):
        self._result = None
        self.dialog.close()

    def _on_submit(self):
        password = self.password_entry.get_text()

        if not password:
            self._show_error("Password cannot be empty")
            return

        if self.verify_fn and not self.verify_fn(password):
            self._show_error("Incorrect password")
            self.password_entry.set_text("")
            self.password_entry.grab_focus()
            return

        # Success
        self._result = password
        self.dialog.close()

    def _show_error(self, message):
        self.error_label.set_text(message)
        self.error_label.set_visible(True)
