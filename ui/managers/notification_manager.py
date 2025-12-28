"""Manages notification display and auto-hide functionality."""

import logging
from typing import Optional

import gi
from gi.repository import GLib, Gtk

gi.require_version("Gtk", "4.0")

logger = logging.getLogger("TFCBM.NotificationManager")


class NotificationManager:
    """Manages notification display with auto-hide."""

    def __init__(self, auto_hide_seconds: int = 10):
        """Initialize NotificationManager.

        Args:
            auto_hide_seconds: Seconds before auto-hiding notification
        """
        self.auto_hide_seconds = auto_hide_seconds
        self._hide_timeout_id: Optional[int] = None

        # Create notification UI
        self.notification_box = self._create_notification_ui()

    def _create_notification_ui(self) -> Gtk.Box:
        """Create and return the notification UI widget.

        Returns:
            Gtk.Box containing the notification label
        """
        # Create notification area
        notification_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        notification_box.set_vexpand(False)
        notification_box.set_hexpand(True)
        notification_box.set_halign(Gtk.Align.FILL)
        notification_box.set_valign(Gtk.Align.END)
        notification_box.set_size_request(-1, 30)  # Narrow strip
        notification_box.add_css_class("notification-area")

        # Create notification label
        self.notification_label = Gtk.Label(label="")
        self.notification_label.set_hexpand(True)
        self.notification_label.set_halign(Gtk.Align.CENTER)
        self.notification_label.set_valign(Gtk.Align.CENTER)
        self.notification_label.set_ellipsize(3)  # PANGO_ELLIPSIZE_END - truncate long text
        notification_box.append(self.notification_label)

        return notification_box

    def show(self, message: str) -> None:
        """Show a notification message in the dedicated area.

        Args:
            message: The message to display
        """
        logger.debug(f"Showing notification: {message}")

        # Cancel any pending auto-hide
        if self._hide_timeout_id is not None:
            GLib.source_remove(self._hide_timeout_id)
            self._hide_timeout_id = None

        # Set message and show
        self.notification_label.set_label(message)
        self.notification_box.set_visible(True)

        logger.debug(
            f"Notification box visible: {self.notification_box.get_visible()}"
        )
        logger.debug(
            f"Notification label visible: {self.notification_label.get_visible()}"
        )
        logger.debug(
            f"Notification box height: {self.notification_box.get_height()}"
        )

        # Schedule auto-hide
        self._hide_timeout_id = GLib.timeout_add_seconds(
            self.auto_hide_seconds, self._hide
        )

    def _hide(self) -> int:
        """Hide the notification area (internal callback).

        Returns:
            GLib.SOURCE_REMOVE to prevent timeout from repeating
        """
        self.notification_box.set_visible(False)
        self.notification_label.set_label("")
        self._hide_timeout_id = None
        return GLib.SOURCE_REMOVE

    def hide(self) -> None:
        """Immediately hide the notification area."""
        # Cancel any pending auto-hide
        if self._hide_timeout_id is not None:
            GLib.source_remove(self._hide_timeout_id)
            self._hide_timeout_id = None

        # Hide immediately
        self._hide()

    def get_widget(self) -> Gtk.Box:
        """Get the notification widget to add to the window.

        Returns:
            The notification box widget
        """
        return self.notification_box
