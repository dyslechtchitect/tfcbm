"""Tests for autostart functionality.

Correct behavior (post-fix):
- Autostart toggle ONLY creates/modifies ~/.config/autostart/*.desktop file
- It does NOT enable/disable the extension in current session
- It does NOT affect current running state
- "Start on Login" only affects NEXT login

Incorrect behavior (pre-fix):
- Autostart toggle called _enable_extension() and _disable_extension()
- This violated GNOME HIG by affecting current session
- Made the toggle confusing and unpredictable
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
from pathlib import Path
import tempfile
import shutil


@pytest.fixture
def temp_autostart_dir():
    """Create a temporary autostart directory for testing."""
    temp_dir = tempfile.mkdtemp()
    autostart_dir = Path(temp_dir) / ".config" / "autostart"
    autostart_dir.mkdir(parents=True)
    yield autostart_dir
    shutil.rmtree(temp_dir)


class TestAutostartBehavior:
    """Test that autostart toggle only affects desktop file, not extension state."""

    @patch('ui.pages.settings_page.Path.home')
    def test_enable_autostart_creates_desktop_file(self, mock_home, temp_autostart_dir):
        """Test that enabling autostart creates the desktop file."""
        from ui.pages.settings_page import SettingsPage

        mock_home.return_value = temp_autostart_dir.parent.parent
        page = SettingsPage(settings=Mock(), on_notification=Mock())

        # Enable autostart
        page._enable_autostart()

        # Check that desktop file was created
        desktop_file = temp_autostart_dir / "io.github.dyslechtchitect.tfcbm.desktop"
        assert desktop_file.exists()

        # Check content
        content = desktop_file.read_text()
        assert "Exec=flatpak run io.github.dyslechtchitect.tfcbm" in content or "Exec=tfcbm" in content
        assert "X-GNOME-Autostart-enabled=true" in content
        assert "Hidden=true" not in content

    @patch('ui.pages.settings_page.Path.home')
    def test_disable_autostart_sets_hidden_true(self, mock_home, temp_autostart_dir):
        """Test that disabling autostart sets Hidden=true in desktop file."""
        from ui.pages.settings_page import SettingsPage

        mock_home.return_value = temp_autostart_dir.parent.parent
        page = SettingsPage(settings=Mock(), on_notification=Mock())

        # First enable
        page._enable_autostart()

        # Then disable
        page._disable_autostart()

        # Check that desktop file has Hidden=true
        desktop_file = temp_autostart_dir / "io.github.dyslechtchitect.tfcbm.desktop"
        content = desktop_file.read_text()
        assert "Hidden=true" in content
        assert "X-GNOME-Autostart-enabled=false" in content

    @patch('ui.pages.settings_page.Path.home')
    @patch('ui.utils.extension_check.subprocess')
    def test_autostart_toggle_does_not_enable_extension(self, mock_subprocess, mock_home, temp_autostart_dir):
        """Test that autostart toggle does NOT call gnome-extensions enable."""
        from ui.pages.settings_page import SettingsPage

        mock_home.return_value = temp_autostart_dir.parent.parent
        mock_switch = Mock()
        mock_switch.get_active.return_value = True

        page = SettingsPage(settings=Mock(), on_notification=Mock())

        # Toggle autostart on
        page._on_autostart_toggled(mock_switch, None)

        # Verify subprocess.run was NOT called (no gnome-extensions command)
        assert mock_subprocess.run.call_count == 0

        # Verify desktop file was created
        desktop_file = temp_autostart_dir / "io.github.dyslechtchitect.tfcbm.desktop"
        assert desktop_file.exists()

    @patch('ui.pages.settings_page.Path.home')
    @patch('ui.utils.extension_check.subprocess')
    def test_autostart_toggle_does_not_disable_extension(self, mock_subprocess, mock_home, temp_autostart_dir):
        """Test that autostart toggle does NOT call gnome-extensions disable."""
        from ui.pages.settings_page import SettingsPage

        mock_home.return_value = temp_autostart_dir.parent.parent
        mock_switch = Mock()

        page = SettingsPage(settings=Mock(), on_notification=Mock())

        # First enable
        mock_switch.get_active.return_value = True
        page._on_autostart_toggled(mock_switch, None)

        # Then disable
        mock_switch.get_active.return_value = False
        page._on_autostart_toggled(mock_switch, None)

        # Verify subprocess.run was NOT called (no gnome-extensions command)
        assert mock_subprocess.run.call_count == 0

        # Verify desktop file has Hidden=true
        desktop_file = temp_autostart_dir / "io.github.dyslechtchitect.tfcbm.desktop"
        content = desktop_file.read_text()
        assert "Hidden=true" in content

    @patch('ui.pages.settings_page.Path.home')
    def test_is_autostart_enabled_detects_hidden_file(self, mock_home, temp_autostart_dir):
        """Test that _is_autostart_enabled returns False for Hidden=true files."""
        from ui.pages.settings_page import SettingsPage

        mock_home.return_value = temp_autostart_dir.parent.parent
        page = SettingsPage(settings=Mock(), on_notification=Mock())

        # Create disabled desktop file
        desktop_file = temp_autostart_dir / "io.github.dyslechtchitect.tfcbm.desktop"
        desktop_file.write_text("""[Desktop Entry]
Type=Application
Name=TFCBM
Exec=tfcbm
Hidden=true
X-GNOME-Autostart-enabled=false
""")

        # Check that it's detected as disabled
        assert page._is_autostart_enabled() is False

    @patch('ui.pages.settings_page.Path.home')
    def test_is_autostart_enabled_detects_enabled_file(self, mock_home, temp_autostart_dir):
        """Test that _is_autostart_enabled returns True for enabled files."""
        from ui.pages.settings_page import SettingsPage

        mock_home.return_value = temp_autostart_dir.parent.parent
        page = SettingsPage(settings=Mock(), on_notification=Mock())

        # Create enabled desktop file
        desktop_file = temp_autostart_dir / "io.github.dyslechtchitect.tfcbm.desktop"
        desktop_file.write_text("""[Desktop Entry]
Type=Application
Name=TFCBM
Exec=flatpak run io.github.dyslechtchitect.tfcbm
X-GNOME-Autostart-enabled=true
""")

        # Check that it's detected as enabled
        assert page._is_autostart_enabled() is True

    @patch('ui.pages.settings_page.Path.home')
    def test_gnome_settings_changes_are_detected(self, mock_home, temp_autostart_dir):
        """Test that changes made by GNOME Settings are properly detected."""
        from ui.pages.settings_page import SettingsPage

        mock_home.return_value = temp_autostart_dir.parent.parent
        page = SettingsPage(settings=Mock(), on_notification=Mock())

        # Create enabled desktop file
        desktop_file = temp_autostart_dir / "io.github.dyslechtchitect.tfcbm.desktop"
        desktop_file.write_text("""[Desktop Entry]
Type=Application
Name=TFCBM
Exec=flatpak run io.github.dyslechtchitect.tfcbm
X-GNOME-Autostart-enabled=true
""")

        assert page._is_autostart_enabled() is True

        # Simulate GNOME Settings disabling it (sets X-GNOME-Autostart-enabled=false)
        desktop_file.write_text("""[Desktop Entry]
Type=Application
Name=TFCBM
Exec=flatpak run io.github.dyslechtchitect.tfcbm
X-GNOME-Autostart-enabled=false
""")

        # Should now detect as disabled
        assert page._is_autostart_enabled() is False


class TestDBusAutoActivationFix:
    """Test that D-Bus service doesn't auto-activate when extension loads.

    This requires the extension to use Gio.DBusProxyFlags.DO_NOT_AUTO_START
    when creating the D-Bus proxy in extension.js _reconnect() method.
    """

    def test_extension_code_uses_do_not_auto_start(self):
        """Test that extension.js uses DO_NOT_AUTO_START flag."""
        extension_js = Path("/home/ron/Documents/git/TFCBM/gnome-extension/extension.js")
        content = extension_js.read_text()

        # Should use DO_NOT_AUTO_START flag
        assert "Gio.DBusProxyFlags.DO_NOT_AUTO_START" in content, \
            "Extension must use DO_NOT_AUTO_START to prevent auto-activation"

        # Should NOT use NONE flag (which triggers auto-activation)
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if "new_for_bus" in line:
                # Check surrounding lines for flag
                context = '\n'.join(lines[max(0, i-5):i+5])
                if "DBUS_NAME" in context:  # This is the TFCBM proxy creation
                    assert "DO_NOT_AUTO_START" in context, \
                        "TFCBM D-Bus proxy must use DO_NOT_AUTO_START"

    def test_dbus_service_file_exists(self):
        """Test that D-Bus service file exists (needed for manual activation)."""
        service_file = Path("/home/ron/Documents/git/TFCBM/io.github.dyslechtchitect.tfcbm.service")
        assert service_file.exists()

        content = service_file.read_text()
        assert "Name=io.github.dyslechtchitect.tfcbm" in content
        assert "Exec=tfcbm" in content


class TestIntegratedBehavior:
    """Test the complete autostart behavior across the system."""

    @patch('ui.pages.settings_page.Path.home')
    def test_user_disables_autostart_app_keeps_running(self, mock_home, temp_autostart_dir):
        """Test that disabling autostart doesn't affect current session.

        Expected behavior:
        1. User has TFCBM running
        2. User toggles "Start on Login" OFF
        3. TFCBM continues running in current session
        4. Desktop file is marked Hidden=true
        5. TFCBM won't start on next login
        """
        from ui.pages.settings_page import SettingsPage

        mock_home.return_value = temp_autostart_dir.parent.parent
        mock_switch = Mock()

        page = SettingsPage(settings=Mock(), on_notification=Mock())

        # Enable first
        mock_switch.get_active.return_value = True
        page._on_autostart_toggled(mock_switch, None)

        # Then disable
        mock_switch.get_active.return_value = False
        page._on_autostart_toggled(mock_switch, None)

        # Notification should mention login (future tense), not current session
        notification_calls = page.on_notification.call_args_list
        disable_notification = str(notification_calls[-1]).lower()
        assert ("next login" in disable_notification or "log in" in disable_notification)
        assert "disabled" not in disable_notification  # Should NOT say extension disabled
