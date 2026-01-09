"""Password authentication service for secrets with one-time operation model."""

import logging
import time
from typing import Optional, Callable

import gi
gi.require_version("Gio", "2.0")
gi.require_version("GLib", "2.0")
from gi.repository import Gio, GLib

logger = logging.getLogger("TFCBM.PasswordService")


class PasswordService:
    """Service for authenticating user to view secrets with one-time operation model."""

    def __init__(self, on_notification: Optional[Callable[[str], None]] = None):
        self.authenticated_until = 0  # Timestamp when authentication expires (5 seconds)
        self.auth_duration = 5  # ONE-TIME operation: 5 seconds timeout
        self.pending_operation = None  # Type of operation pending (copy, view, save, etc.)
        self.pending_item_id = None  # Item ID this auth is for
        self._timeout_id = None  # GLib timeout ID for auto-clear
        self.on_notification = on_notification if on_notification else (lambda msg: logger.info(f"Notification: {msg}"))

    def is_authenticated_for(self, operation: str, item_id: int) -> bool:
        """
        Check if user is authenticated for a specific operation on a specific item.

        Args:
            operation: Operation type (e.g., "copy", "view", "save", "toggle_secret", "drag")
            item_id: Item ID this operation is for

        Returns:
            True if authenticated for THIS operation on THIS item, False otherwise
        """
        if time.time() >= self.authenticated_until:
            # Timeout expired
            self._clear_pending()
            return False

        # Must match both operation and item
        is_auth = (self.pending_operation == operation and
                  self.pending_item_id == item_id)

        if not is_auth:
            logger.info(f"[AUTH] Auth mismatch: pending={self.pending_operation}/{self.pending_item_id}, requested={operation}/{item_id}")

        return is_auth

    def authenticate_for(self, operation: str, item_id: int, parent_window=None) -> bool:
        """
        Authenticate for ONE specific operation on ONE specific item using the Secret portal.

        Args:
            operation: Operation type (e.g., "copy", "view", "save")
            item_id: Item ID this auth is for
            parent_window: Parent window (for portal interaction, if required by the portal)

        Returns:
            True if authentication successful, False otherwise
        """
        logger.info(f"[AUTH] Requesting authentication for {operation} on item {item_id} via Secret portal")

        # Clear any existing authentication first
        self._clear_pending()

        try:
            # Connect to the Secret portal
            portal = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SESSION,
                Gio.DBusProxyFlags.NONE,
                None,  # GDBusInterfaceInfo
                'org.freedesktop.portal.Secret',
                '/org/freedesktop/portal/desktop',  # Standard path for desktop portals
                'org.freedesktop.portal.Secret',
                None,  # Cancellable
            )

            # We'll use a dummy secret for authentication. The portal will prompt the user
            # to unlock their keyring if necessary. The 'secret_id' here is just a unique string.
            secret_id = "tfcbm-authentication-dummy-secret"
            options = GLib.Variant('a{sv}', {
                'handle': GLib.Variant('s', 'tfcbm-auth-handle') # Optional handle for portal response
            })

            # RetrieveSecret will trigger a password prompt via the secret service if needed
            # The response will contain the secret, but we only care if it succeeded
            # as a proxy for user authentication.
            response = portal.call_sync(
                'RetrieveSecret',
                GLib.Variant('(s@a{sv})', (secret_id, options)),
                Gio.DBusCallFlags.NONE,
                -1,  # Timeout
                None, # GCancellable
            )

            # The response is a tuple (handle, secret_raw)
            # If successful, response is not None and contains data.
            # The critical part is that the user went through the authentication process.
            if response is not None and response.n_children() > 0:
                logger.info(f"[AUTH] Authentication successful via Secret portal")

                # Authentication successful - set up one-time operation
                self.pending_operation = operation
                self.pending_item_id = item_id
                self.authenticated_until = time.time() + self.auth_duration

                # Set up auto-clear after 5 seconds
                self._schedule_auto_clear()
                return True
            else:
                logger.info(f"[AUTH] Authentication failed or cancelled via Secret portal (no response or empty response)")
                return False

        except GLib.Error as e:
            logger.error(f"[AUTH] D-Bus error with Secret portal: {e.message}")
            if "org.freedesktop.portal.Error.NotFound" in e.message:
                self.on_notification(
                    "Secret portal not found. Please ensure xdg-desktop-portal-gnome (or similar) is running."
                )
            elif "authentication was cancelled" in e.message:
                 logger.info(f"[AUTH] User cancelled authentication via Secret portal")
            else:
                self.on_notification(f"Error authenticating: {e.message}")
            return False
        except Exception as e:
            logger.error(f"[AUTH] Unexpected error during Secret portal authentication: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            self.on_notification(f"Unexpected error during authentication: {e}")
            return False

    def consume_authentication(self, operation: str, item_id: int) -> bool:
        """
        Consume (use up) the authentication for an operation.
        This should be called immediately after the operation completes.

        Args:
            operation: Operation type that was performed
            item_id: Item ID the operation was for

        Returns:
            True if authentication was valid and consumed, False otherwise
        """
        if self.is_authenticated_for(operation, item_id):
            logger.info(f"[AUTH] Consuming authentication for {operation} on item {item_id}")
            self._clear_pending()
            return True
        return False

    def clear_authentication(self):
        """Clear authentication state immediately (e.g., when clicking elsewhere or window loses focus)."""
        logger.info(f"[AUTH] Clearing authentication (focus lost or user clicked elsewhere)")
        self._clear_pending()

    def _clear_pending(self):
        """Internal method to clear pending authentication."""
        self.authenticated_until = 0
        self.pending_operation = None
        self.pending_item_id = None

        # Cancel auto-clear timeout if exists
        if self._timeout_id:
            from gi.repository import GLib
            GLib.source_remove(self._timeout_id)
            self._timeout_id = None

    def _schedule_auto_clear(self):
        """Schedule automatic clear after timeout."""
        from gi.repository import GLib

        # Cancel existing timeout if any
        if self._timeout_id:
            GLib.source_remove(self._timeout_id)

        # Schedule new timeout
        self._timeout_id = GLib.timeout_add(
            self.auth_duration * 1000,  # Convert to milliseconds
            self._on_timeout
        )

    def _on_timeout(self):
        """Called when authentication times out."""
        logger.info(f"[AUTH] Authentication timed out after {self.auth_duration} seconds")
        self._clear_pending()
        return False  # Don't repeat
