"""Password authentication service for secrets with one-time operation model."""

import subprocess
import time
from typing import Optional


class PasswordService:
    """Service for authenticating user to view secrets with one-time operation model."""

    def __init__(self):
        self.authenticated_until = 0  # Timestamp when authentication expires (5 seconds)
        self.auth_duration = 5  # ONE-TIME operation: 5 seconds timeout
        self.pending_operation = None  # Type of operation pending (copy, view, save, etc.)
        self.pending_item_id = None  # Item ID this auth is for
        self._timeout_id = None  # GLib timeout ID for auto-clear

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
            print(f"[AUTH] Auth mismatch: pending={self.pending_operation}/{self.pending_item_id}, requested={operation}/{item_id}")

        return is_auth

    def authenticate_for(self, operation: str, item_id: int, parent_window=None) -> bool:
        """
        Authenticate for ONE specific operation on ONE specific item.

        Args:
            operation: Operation type (e.g., "copy", "view", "save")
            item_id: Item ID this auth is for
            parent_window: Parent window (ignored, kept for API compatibility)

        Returns:
            True if authentication successful, False otherwise
        """
        print(f"[AUTH] Requesting authentication for {operation} on item {item_id}")

        # Clear any existing authentication first
        self._clear_pending()

        # Use pkexec for native PolicyKit authentication dialog
        try:
            result = subprocess.run(
                [
                    'pkexec',
                    '--user', subprocess.run(['whoami'], capture_output=True, text=True).stdout.strip(),
                    '/bin/true'
                ],
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:
                # Authentication successful - set up one-time operation
                self.pending_operation = operation
                self.pending_item_id = item_id
                self.authenticated_until = time.time() + self.auth_duration

                # Set up auto-clear after 5 seconds
                self._schedule_auto_clear()

                print(f"[AUTH] Authentication successful for {operation} on item {item_id}, expires in {self.auth_duration}s")
                return True
            else:
                # Authentication failed or cancelled
                print(f"[AUTH] Authentication failed")
                return False

        except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
            print(f"[AUTH] Password prompt failed: {e}")
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
            print(f"[AUTH] Consuming authentication for {operation} on item {item_id}")
            self._clear_pending()
            return True
        return False

    def clear_authentication(self):
        """Clear authentication state immediately (e.g., when clicking elsewhere or window loses focus)."""
        print(f"[AUTH] Clearing authentication (focus lost or user clicked elsewhere)")
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
        print(f"[AUTH] Authentication timed out after {self.auth_duration} seconds")
        self._clear_pending()
        return False  # Don't repeat
