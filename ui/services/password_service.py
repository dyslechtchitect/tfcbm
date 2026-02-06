"""Password authentication service for secrets with one-time operation model.

Uses a native GTK4 password dialog to collect the user's system password,
then verifies it via unix_chkpwd (the standard PAM helper).
Fully DE-agnostic — no pkexec, no polkit agent required.
"""

import logging
import os
import subprocess
import time

logger = logging.getLogger("TFCBM.PasswordService")


class PasswordService:
    """Service for authenticating user to access secrets with one-time operation model."""

    def __init__(self, on_notification=None):
        self.authenticated_until = 0  # Timestamp when authentication expires
        self.auth_duration = 5  # ONE-TIME operation: 5 seconds timeout
        self.pending_operation = None  # Type of operation pending
        self.pending_item_id = None  # Item ID this auth is for
        self._timeout_id = None  # GLib timeout ID for auto-clear
        self.on_notification = on_notification

    # --- System password verification ---

    def _verify_system_password(self, password: str) -> bool:
        """Verify a password against the system.

        Primary: sudo -S -k (uses the full PAM stack — works with shadow,
        SSSD, systemd-homed, etc.).  Fallback: unix_chkpwd (direct shadow
        check, may be blocked by SELinux on Fedora).
        """
        from gi.repository import GLib

        username = GLib.get_user_name()
        in_flatpak = os.path.exists("/.flatpak-info")
        host = ["flatpak-spawn", "--host"] if in_flatpak else []

        logger.info(f"[AUTH] Verifying system password for {username}")

        # --- Primary: sudo -S -k ---
        try:
            result = subprocess.run(
                host + ["sudo", "-S", "-k", "/bin/true"],
                input=password + "\n",
                capture_output=True,
                text=True,
                timeout=10,
            )
            # Always clear sudo timestamp so we don't leave a cached session
            try:
                subprocess.run(
                    host + ["sudo", "-k"],
                    capture_output=True,
                    timeout=5,
                )
            except Exception:
                pass

            logger.info(f"[AUTH] sudo returned {result.returncode}")

            if result.returncode == 0:
                return True

            # If the user isn't in sudoers, fall through to unix_chkpwd
            stderr = result.stderr or ""
            if "sudoers" in stderr:
                logger.info("[AUTH] User not in sudoers, trying unix_chkpwd")
            else:
                return False  # Wrong password

        except FileNotFoundError:
            logger.info("[AUTH] sudo not found, trying unix_chkpwd")
        except subprocess.TimeoutExpired:
            logger.error("[AUTH] sudo timed out, trying unix_chkpwd")
        except Exception as e:
            logger.error(f"[AUTH] sudo error ({e}), trying unix_chkpwd")

        # --- Fallback: unix_chkpwd ---
        try:
            result = subprocess.run(
                host + ["/usr/sbin/unix_chkpwd", username],
                input=password,
                capture_output=True,
                text=True,
                timeout=10,
            )
            logger.info(f"[AUTH] unix_chkpwd returned {result.returncode}")
            return result.returncode == 0
        except FileNotFoundError:
            logger.error("[AUTH] Neither sudo nor unix_chkpwd available")
            return False
        except Exception as e:
            logger.error(f"[AUTH] unix_chkpwd error: {e}")
            return False

    # --- Authentication ---

    def is_authenticated_for(self, operation: str, item_id: int) -> bool:
        """Check if user is authenticated for a specific operation on a specific item.

        Args:
            operation: Operation type (e.g., "copy", "view", "save", "toggle_secret", "drag")
            item_id: Item ID this operation is for

        Returns:
            True if authenticated for THIS operation on THIS item, False otherwise
        """
        if time.time() >= self.authenticated_until:
            self._clear_pending()
            return False

        is_auth = (
            self.pending_operation == operation
            and self.pending_item_id == item_id
        )

        if not is_auth:
            logger.info(
                f"[AUTH] Auth mismatch: pending={self.pending_operation}/{self.pending_item_id}, "
                f"requested={operation}/{item_id}"
            )

        return is_auth

    def authenticate_for(self, operation: str, item_id: int, parent_window=None) -> bool:
        """Authenticate for ONE specific operation on ONE specific item.

        Shows a native GTK4 password dialog and verifies the system password.

        Args:
            operation: Operation type (e.g., "copy", "view", "save")
            item_id: Item ID this auth is for
            parent_window: Parent window for the modal dialog

        Returns:
            True if authentication successful, False otherwise
        """
        logger.info(f"[AUTH] Requesting authentication for {operation} on item {item_id}")

        self._clear_pending()

        from ui.dialogs.password_dialog import PasswordDialog

        try:
            dialog = PasswordDialog(
                parent_window,
                verify_fn=self._verify_system_password,
            )
            password = dialog.run()

            if password is None:
                logger.info("[AUTH] Authentication cancelled")
                return False

            # Authentication successful — set up one-time operation
            self.pending_operation = operation
            self.pending_item_id = item_id
            self.authenticated_until = time.time() + self.auth_duration
            self._schedule_auto_clear()

            logger.info(
                f"[AUTH] Authentication successful for {operation} on item {item_id}, "
                f"expires in {self.auth_duration}s"
            )
            return True

        except Exception as e:
            logger.error(f"[AUTH] Unexpected error: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return False

    def consume_authentication(self, operation: str, item_id: int) -> bool:
        """Consume (use up) the authentication for an operation.
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
        """Clear authentication state immediately (e.g., on focus loss)."""
        logger.info("[AUTH] Clearing authentication (focus lost or user clicked elsewhere)")
        self._clear_pending()

    def _clear_pending(self):
        """Internal method to clear pending authentication."""
        self.authenticated_until = 0
        self.pending_operation = None
        self.pending_item_id = None

        if self._timeout_id:
            from gi.repository import GLib
            GLib.source_remove(self._timeout_id)
            self._timeout_id = None

    def _schedule_auto_clear(self):
        """Schedule automatic clear after timeout."""
        from gi.repository import GLib

        if self._timeout_id:
            GLib.source_remove(self._timeout_id)

        self._timeout_id = GLib.timeout_add(
            self.auth_duration * 1000,
            self._on_timeout,
        )

    def _on_timeout(self):
        """Called when authentication times out."""
        logger.info(f"[AUTH] Authentication timed out after {self.auth_duration} seconds")
        self._clear_pending()
        return False  # Don't repeat
