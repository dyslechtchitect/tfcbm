"""ItemSecretManager - Handles secret status toggling for clipboard items.

This handler manages:
- Toggling secret status on/off
- Authentication for unmarking secrets
- Confirmation dialog for unmarking
- Naming dialog for marking items without names
"""

import logging

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk

from ui.dialogs import SecretNamingDialog

logger = logging.getLogger("TFCBM.UI")


class ItemSecretManager:
    """Handles secret status management for clipboard items."""

    def __init__(
        self,
        item: dict,
        window,
        password_service,
        ws_service,
        get_root: callable,
    ):
        """Initialize the secret manager.

        Args:
            item: The clipboard item data dictionary
            window: The window instance for notifications
            password_service: PasswordService for authentication
            ipc_service: ItemIPCService for toggling secret status
            get_root: Callback to get the root window for dialog presentation
        """
        self.item = item
        self.window = window
        self.password_service = password_service
        self.ipc_service = ws_service
        self.get_root = get_root

    def handle_secret_action(self):
        """Handle secret button click - toggle secret status."""
        item_id = self.item.get("id")
        current_is_secret = self.item.get("is_secret", False)
        item_name = self.item.get("name")

        # If currently a secret, require authentication before unmarking
        if current_is_secret:
            logger.info(
                f"Item {item_id} is secret, checking authentication for unmark"
            )
            # Check if authenticated for THIS specific toggle_secret operation on THIS item
            if not self.password_service.is_authenticated_for(
                "toggle_secret", item_id
            ):
                logger.info("Not authenticated for unmark, prompting for password")
                # Prompt for authentication for THIS operation on THIS item
                if not self.password_service.authenticate_for(
                    "toggle_secret", item_id, self.get_root()
                ):
                    logger.info("Authentication failed or cancelled for unmark")
                    self.window.show_notification(
                        "Authentication required to unmark protected item"
                    )
                    return
                else:
                    logger.info("Authentication successful for unmark")
            else:
                logger.info("Already authenticated for unmark")

            # Show confirmation dialog after authentication
            dialog = Gtk.MessageDialog(
                transient_for=self.get_root(),
                modal=True,
                message_type=Gtk.MessageType.WARNING,
                buttons=Gtk.ButtonsType.NONE,
                text="Unmark as Protected?",
                secondary_text="Are you sure you want to remove protection from this item? The content will become visible.",
            )
            dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
            dialog.add_button("Unmark as Protected", Gtk.ResponseType.OK)
            ok_button = dialog.get_widget_for_response(Gtk.ResponseType.OK)
            ok_button.add_css_class("destructive-action")

            def on_response(dialog_obj, response):
                dialog_obj.close()
                if response == Gtk.ResponseType.OK:
                    self.ipc_service.toggle_secret_status(item_id, False, item_name)
                # Consume authentication regardless of user choice (confirm or cancel)
                self.password_service.consume_authentication("toggle_secret", item_id)

            dialog.connect("response", on_response)
            dialog.present()

        # If marking as secret and item has no name, show naming dialog
        elif not item_name:

            def on_name_provided(name):
                self.ipc_service.toggle_secret_status(item_id, True, name)

            dialog = SecretNamingDialog(self.get_root(), on_name_provided)
            dialog.show()
        else:
            # Item already has name, just mark as secret
            self.ipc_service.toggle_secret_status(item_id, True, item_name)
