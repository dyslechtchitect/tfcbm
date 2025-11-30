"""Password authentication service for secrets."""

import subprocess
import time


class PasswordService:
    """Service for authenticating user to view secrets."""

    def __init__(self):
        self.authenticated_until = 0  # Timestamp when authentication expires
        self.auth_duration = 300  # 5 minutes in seconds

    def is_authenticated(self) -> bool:
        """Check if user is currently authenticated."""
        return time.time() < self.authenticated_until

    def authenticate(self, parent_window=None) -> bool:
        """
        Prompt user for system password using native PolicyKit authentication.

        Args:
            parent_window: Parent window (ignored, kept for API compatibility)

        Returns:
            True if authentication successful, False otherwise
        """
        # If already authenticated, extend the session
        if self.is_authenticated():
            self.authenticated_until = time.time() + self.auth_duration
            return True

        # Use pkexec for native PolicyKit authentication dialog
        try:
            # pkexec will show the native GNOME authentication dialog
            # We run a simple command (/bin/true) to verify authentication
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
                # Authentication successful
                self.authenticated_until = time.time() + self.auth_duration
                return True
            else:
                # Authentication failed or cancelled
                return False

        except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
            print(f"Password prompt failed: {e}")
            return False

    def clear_authentication(self):
        """Clear authentication state (e.g., when window loses focus)."""
        self.authenticated_until = 0
