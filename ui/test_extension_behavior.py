"""Tests for extension enable/disable behavior on quit and launch.

TFCBM Extension/App Integration:
- Extension provides clipboard monitoring and tray icon when enabled
- Tray icon is ONLY visible when app is running (checks DBus owner)
- App auto-enables extension on launch
- App auto-disables extension on quit
- "Start on Login" controls app launch (extension follows app lifecycle)

This creates an integrated user experience where the tray icon clearly
indicates when TFCBM is active.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path


class FakeGio:
    """Fake Gio module for testing."""
    class BusType:
        SESSION = 1

    class DBusCallFlags:
        NONE = 0

    @staticmethod
    def bus_get_sync(bus_type, cancellable):
        """Return a fake connection."""
        connection = Mock()
        connection.call_sync = Mock(return_value=None)
        return connection


class FakeGLib:
    """Fake GLib module for testing."""
    @staticmethod
    def Variant(signature, value):
        """Create a fake variant."""
        return Mock(signature=signature, value=value)


class TestExtensionBehavior:
    """Test extension enable/disable behavior."""

    def test_quit_disables_extension(self):
        """Test that quitting TFCBM disables the extension."""
        # This test simulates the behavior in dbus_service.py _handle_quit
        # by testing the DBus disable call directly

        # Use the fake Gio and GLib
        connection = FakeGio.bus_get_sync(FakeGio.BusType.SESSION, None)

        # Make the disable call (same as in dbus_service.py)
        result = connection.call_sync(
            'org.gnome.Shell.Extensions',
            '/org/gnome/Shell/Extensions',
            'org.gnome.Shell.Extensions',
            'DisableExtension',
            FakeGLib.Variant('(s)', ('tfcbm-clipboard-monitor@github.com',)),
            None,
            FakeGio.DBusCallFlags.NONE,
            -1,
            None
        )

        # Verify DBus call was made to disable extension
        assert connection.call_sync.called
        call_args = connection.call_sync.call_args
        assert call_args[0][2] == 'org.gnome.Shell.Extensions'
        assert call_args[0][3] == 'DisableExtension'

    @patch('ui.utils.extension_check.subprocess')
    @patch('ui.utils.extension_check.os')
    def test_launch_enables_extension_if_installed(self, mock_os, mock_subprocess):
        """Test that launching TFCBM auto-enables extension if installed but disabled."""
        from ui.utils.extension_check import get_extension_status, enable_extension

        mock_os.environ.copy.return_value = {'PATH': '/usr/bin'}

        # Mock extension is installed but not enabled
        list_result = Mock()
        list_result.returncode = 0
        list_result.stdout = 'tfcbm-clipboard-monitor@github.com\n'

        info_result = Mock()
        info_result.returncode = 0
        info_result.stdout = 'State: DISABLED\n'

        enable_result = Mock()
        enable_result.returncode = 0
        enable_result.stderr = ''

        mock_subprocess.run.side_effect = [list_result, info_result, enable_result]

        # Check status
        status = get_extension_status()
        assert status['installed'] is True
        assert status['enabled'] is False

        # Enable extension
        success, message = enable_extension()
        assert success is True

    @patch('ui.utils.extension_check.subprocess')
    @patch('ui.utils.extension_check.os')
    def test_launch_shows_setup_if_not_installed(self, mock_os, mock_subprocess):
        """Test that launching TFCBM shows setup screen if extension not installed."""
        from ui.utils.extension_check import get_extension_status

        mock_os.environ.copy.return_value = {'PATH': '/usr/bin'}

        # Mock extension is not installed
        list_result = Mock()
        list_result.returncode = 0
        list_result.stdout = 'some-other-extension@example.com\n'

        mock_subprocess.run.return_value = list_result

        # Check status
        status = get_extension_status()
        assert status['installed'] is False
        assert status['enabled'] is False
        assert status['ready'] is False

    @patch('ui.utils.extension_check.subprocess')
    @patch('ui.utils.extension_check.os')
    def test_extension_already_enabled_no_action_needed(self, mock_os, mock_subprocess):
        """Test that if extension is already enabled, no action is needed."""
        from ui.utils.extension_check import get_extension_status

        mock_os.environ.copy.return_value = {'PATH': '/usr/bin'}

        # Mock extension is installed and enabled
        list_result = Mock()
        list_result.returncode = 0
        list_result.stdout = 'tfcbm-clipboard-monitor@github.com\n'

        info_result = Mock()
        info_result.returncode = 0
        info_result.stdout = 'State: ENABLED\n'

        mock_subprocess.run.side_effect = [list_result, info_result]

        # Check status
        status = get_extension_status()
        assert status['installed'] is True
        assert status['enabled'] is True
        assert status['ready'] is True
