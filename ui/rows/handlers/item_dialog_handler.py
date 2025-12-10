"""ItemDialogHandler - Handles all dialog operations for clipboard items.

This handler manages:
- View dialog for full item display
- Save dialog for exporting items to files
- Delete confirmation dialog
- Authentication for secret items before dialogs
"""

import base64
import logging
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Gio", "2.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, GdkPixbuf, Gio, GLib, Gtk, Pango

logger = logging.getLogger("TFCBM.UI")


class ItemDialogHandler:
    """Handles dialog operations for clipboard items."""

    def __init__(
        self,
        item: dict,
        window,
        password_service,
        ws_service,
        get_root: callable,
    ):
        """Initialize the dialog handler.

        Args:
            item: The clipboard item data dictionary
            window: The window instance for notifications
            password_service: PasswordService for authentication
            ws_service: ItemWebSocketService for fetching secret content
            get_root: Callback to get the root window for dialog presentation
        """
        self.item = item
        self.window = window
        self.password_service = password_service
        self.ws_service = ws_service
        self.get_root = get_root

    def handle_view_action(self):
        """Handle view button click - show full item dialog."""
        # Check if item is secret and require authentication
        is_secret = self.item.get("is_secret", False)
        item_id = self.item.get("id")

        if is_secret:
            logger.info(f"Item {item_id} is secret, checking authentication for view")
            # Check if authenticated for THIS specific view operation on THIS item
            if not self.password_service.is_authenticated_for("view", item_id):
                logger.info("Not authenticated for view, prompting for password")
                # Prompt for authentication for THIS operation on THIS item
                if not self.password_service.authenticate_for(
                    "view", item_id, self.get_root()
                ):
                    logger.info("Authentication failed or cancelled for view")
                    self.window.show_notification(
                        "Authentication required to view secret"
                    )
                    return
                else:
                    logger.info("Authentication successful for view")
            else:
                logger.info("Already authenticated for view")

            # Fetch real content for viewing
            logger.info(f"Fetching real content for secret item {item_id} for view")
            real_content = self.ws_service.fetch_secret_content(item_id)
            if not real_content:
                self.window.show_notification("Failed to retrieve secret content")
                # Consume authentication even on failure
                self.password_service.consume_authentication("view", item_id)
                return
            logger.info(
                f"Retrieved secret content for view (length: {len(str(real_content))})"
            )

            # Temporarily replace content for viewing
            original_content = self.item.get("content")
            self.item["content"] = real_content
            self.show_view_dialog()
            # Restore placeholder
            self.item["content"] = original_content
            # Consume authentication after successful view
            self.password_service.consume_authentication("view", item_id)
        else:
            self.show_view_dialog()

    def handle_save_action(self):
        """Handle save button click - show save file dialog."""
        # Check if item is secret and require authentication
        is_secret = self.item.get("is_secret", False)
        item_id = self.item.get("id")

        if is_secret:
            logger.info(f"Item {item_id} is secret, checking authentication for save")
            # Check if authenticated for THIS specific save operation on THIS item
            if not self.password_service.is_authenticated_for("save", item_id):
                logger.info("Not authenticated for save, prompting for password")
                # Prompt for authentication for THIS operation on THIS item
                if not self.password_service.authenticate_for(
                    "save", item_id, self.get_root()
                ):
                    logger.info("Authentication failed or cancelled for save")
                    self.window.show_notification(
                        "Authentication required to save secret"
                    )
                    return
                else:
                    logger.info("Authentication successful for save")
            else:
                logger.info("Already authenticated for save")

            # Fetch real content for saving
            logger.info(f"Fetching real content for secret item {item_id} for save")
            real_content = self.ws_service.fetch_secret_content(item_id)
            if not real_content:
                self.window.show_notification("Failed to retrieve secret content")
                # Consume authentication even on failure
                self.password_service.consume_authentication("save", item_id)
                return
            logger.info(
                f"Retrieved secret content for save (length: {len(str(real_content))})"
            )

            # Temporarily replace content for saving
            original_content = self.item.get("content")
            self.item["content"] = real_content
            self.show_save_dialog()
            # Restore placeholder
            self.item["content"] = original_content
            # Consume authentication after successful save
            self.password_service.consume_authentication("save", item_id)
        else:
            self.show_save_dialog()

    def handle_delete_action(self):
        """Handle delete button click - show confirmation dialog."""
        window = self.get_root()

        # Create confirmation dialog
        dialog = Adw.AlertDialog.new(
            "Delete this item?",
            "This item will be permanently removed from your clipboard history.",
        )

        dialog.add_response("cancel", "Nah")
        dialog.add_response("delete", "Yeah")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        def on_response(dialog, response):
            if response == "delete":
                self.ws_service.delete_item_from_server(self.item["id"])

        dialog.connect("response", on_response)
        dialog.present(window)

    def show_save_dialog(self):
        """Show file save dialog."""
        item_type = self.item["type"]

        # Create file chooser dialog
        dialog = Gtk.FileDialog()

        # Set default filename based on type
        custom_name = self.item.get("name")
        if item_type == "text" or item_type == "url":
            filename = (
                f"{custom_name}.txt"
                if custom_name and not custom_name.endswith(".txt")
                else custom_name
                or ("url.txt" if item_type == "url" else "clipboard.txt")
            )
            dialog.set_initial_name(filename)
        elif item_type.startswith("image/"):
            ext = item_type.split("/")[-1]
            filename = (
                f"{custom_name}.{ext}"
                if custom_name and not custom_name.endswith(f".{ext}")
                else custom_name or f"clipboard.{ext}"
            )
            dialog.set_initial_name(filename)
        elif item_type == "screenshot":
            filename = (
                f"{custom_name}.png"
                if custom_name and not custom_name.endswith(".png")
                else custom_name or "screenshot.png"
            )
            dialog.set_initial_name(filename)

        window = self.get_root()

        def on_save_finish(dialog_obj, result):
            try:
                file = dialog_obj.save_finish(result)
                if file:
                    path = file.get_path()
                    if item_type == "text" or item_type == "url":
                        with open(path, "w") as f:
                            f.write(self.item["content"])
                        logger.info(
                            f"Saved {'URL' if item_type == 'url' else 'text'} to {path}"
                        )
                    elif item_type.startswith("image/") or item_type == "screenshot":
                        # Save image from base64 data
                        image_data = base64.b64decode(self.item["content"])
                        with open(path, "wb") as f:
                            f.write(image_data)
                        logger.info(f"Saved image to {path}")
            except Exception as e:
                logger.error(f"Error saving file: {e}")

        dialog.save(window, None, on_save_finish)

    def show_view_dialog(self):
        """Show full item view dialog."""
        item_type = self.item["type"]
        window = self.get_root()

        dialog = Adw.Window(modal=True, transient_for=window)
        dialog.set_title("Full Clipboard Item")
        dialog.set_default_size(800, 600)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        main_box.set_margin_start(18)
        main_box.set_margin_end(18)
        main_box.set_margin_top(12)
        main_box.set_margin_bottom(12)

        # Header with close button
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        header_box.set_hexpand(True)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        header_box.append(spacer)

        close_button = Gtk.Button()
        close_button.set_icon_name("window-close-symbolic")
        close_button.set_tooltip_text("Close")
        close_button.connect("clicked", lambda btn: dialog.close())
        header_box.append(close_button)

        main_box.append(header_box)

        # Content area
        content_scroll = Gtk.ScrolledWindow()
        content_scroll.set_vexpand(True)
        content_scroll.set_hexpand(True)

        if item_type == "text" or item_type == "url":
            content_label = Gtk.Label(label=self.item["content"])
            content_label.set_wrap(True)
            content_label.set_selectable(True)
            content_label.set_halign(Gtk.Align.START)
            content_label.set_valign(Gtk.Align.START)
            content_scroll.set_child(content_label)

        elif item_type.startswith("image/") or item_type == "screenshot":
            image_data = base64.b64decode(self.item["content"])
            loader = GdkPixbuf.PixbufLoader()
            loader.write(image_data)
            loader.close()
            pixbuf = loader.get_pixbuf()
            texture = Gdk.Texture.new_for_pixbuf(pixbuf)

            picture = Gtk.Picture.new_for_paintable(texture)
            picture.set_halign(Gtk.Align.CENTER)
            picture.set_valign(Gtk.Align.CENTER)
            picture.set_content_fit(Gtk.ContentFit.CONTAIN)
            content_scroll.set_child(picture)

        elif item_type == "file":
            file_metadata = self.item.get("content", {})
            is_directory = file_metadata.get("is_directory", False)
            original_path = file_metadata.get("original_path", "")

            if is_directory and original_path and Path(original_path).exists():
                # Show folder contents with FileChooserWidget
                folder_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)

                # Info label
                info_label = Gtk.Label()
                folder_name = file_metadata.get("name", "Folder")
                info_label.set_markup(
                    f"<b>Folder:</b> {GLib.markup_escape_text(folder_name)}"
                )
                info_label.set_halign(Gtk.Align.START)
                folder_box.append(info_label)

                # Path label
                path_label = Gtk.Label(label=original_path)
                path_label.add_css_class("caption")
                path_label.add_css_class("dim-label")
                path_label.set_halign(Gtk.Align.START)
                path_label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
                folder_box.append(path_label)

                # FileChooserWidget to show folder tree
                file_chooser = Gtk.FileChooserWidget(action=Gtk.FileChooserAction.OPEN)
                file_chooser.set_current_folder(Gio.File.new_for_path(original_path))
                file_chooser.set_vexpand(True)
                file_chooser.set_hexpand(True)

                folder_box.append(file_chooser)
                content_scroll.set_child(folder_box)
            else:
                # Regular file or folder doesn't exist
                file_info_box = Gtk.Box(
                    orientation=Gtk.Orientation.VERTICAL, spacing=12
                )
                file_info_box.set_valign(Gtk.Align.CENTER)
                file_info_box.set_halign(Gtk.Align.CENTER)

                file_name = file_metadata.get("name", "Unknown file")
                name_label = Gtk.Label()
                name_label.set_markup(f"<b>{GLib.markup_escape_text(file_name)}</b>")
                file_info_box.append(name_label)

                if original_path:
                    if not Path(original_path).exists():
                        error_label = Gtk.Label(
                            label="File/folder no longer exists at original location"
                        )
                        error_label.add_css_class("dim-label")
                        file_info_box.append(error_label)

                    path_label = Gtk.Label(label=original_path)
                    path_label.add_css_class("caption")
                    path_label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
                    path_label.set_max_width_chars(50)
                    file_info_box.append(path_label)

                # File metadata details
                details_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
                details_box.set_margin_top(12)

                file_size = file_metadata.get("size", 0)
                if file_size > 0:
                    size_mb = file_size / (1024 * 1024)
                    size_label = Gtk.Label(label=f"Size: {size_mb:.2f} MB")
                    size_label.add_css_class("caption")
                    details_box.append(size_label)

                mime_type = file_metadata.get("mime_type", "")
                if mime_type:
                    type_label = Gtk.Label(label=f"Type: {mime_type}")
                    type_label.add_css_class("caption")
                    details_box.append(type_label)

                file_info_box.append(details_box)
                content_scroll.set_child(file_info_box)

        main_box.append(content_scroll)
        dialog.set_content(main_box)
        dialog.present()
