"""Dialog for naming secret items."""

from typing import Callable, Optional

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk


class SecretNamingDialog:
    """Dialog to prompt user for a name when marking item as secret."""

    def __init__(self, parent_window: Gtk.Window, on_save: Callable[[str], None]):
        """
        Initialize the naming dialog.

        Args:
            parent_window: Parent window for the dialog
            on_save: Callback function to call with the name when saved
        """
        self.parent_window = parent_window
        self.on_save = on_save

    def show(self):
        """Show the naming dialog."""
        dialog = Gtk.MessageDialog(
            transient_for=self.parent_window,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.NONE,
            text="Name Required",
            secondary_text="Protected items must be named. Please enter a name for this item.",
        )

        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Save", Gtk.ResponseType.OK)
        ok_button = dialog.get_widget_for_response(Gtk.ResponseType.OK)
        ok_button.add_css_class("suggested-action")

        # Create content box
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content_box.set_margin_top(12)
        content_box.set_margin_bottom(12)
        content_box.set_margin_start(12)
        content_box.set_margin_end(12)

        # Name entry
        name_entry = Gtk.Entry()
        name_entry.set_placeholder_text("Enter a name for this protected item...")
        name_entry.set_hexpand(True)

        # Focus the entry when dialog shows
        def on_map(widget):
            name_entry.grab_focus()

        content_box.connect("map", on_map)

        content_box.append(name_entry)

        message_area = dialog.get_message_area()
        message_area.append(content_box)

        def on_response(dialog_obj, response):
            if response == Gtk.ResponseType.OK:
                name = name_entry.get_text().strip()
                print(f"[SecretNamingDialog] Save clicked, name: '{name}'")
                if name:
                    print(f"[SecretNamingDialog] Calling on_save callback with name: '{name}'")
                    dialog_obj.close()
                    self.on_save(name)
                else:
                    # Show error if name is empty
                    print("[SecretNamingDialog] Name is empty, showing error")
                    error_dialog = Gtk.MessageDialog(
                        transient_for=self.parent_window,
                        modal=True,
                        message_type=Gtk.MessageType.ERROR,
                        buttons=Gtk.ButtonsType.OK,
                        text="Name Required",
                        secondary_text="Please enter a non-empty name for this protected item.",
                    )
                    error_dialog.connect("response", lambda d, r: d.close())
                    error_dialog.present()
                    return  # Don't close the main dialog
            else:
                dialog_obj.close()

        dialog.connect("response", on_response)

        # Allow Enter key to save
        def on_activate(entry):
            name = entry.get_text().strip()
            print(f"[SecretNamingDialog] Enter key pressed, name: '{name}'")
            if name:
                print(f"[SecretNamingDialog] Closing dialog and calling on_save callback with name: '{name}'")
                dialog.close()
                self.on_save(name)
            else:
                print("[SecretNamingDialog] Enter pressed but name is empty")

        name_entry.connect("activate", on_activate)

        dialog.present()
