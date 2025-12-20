"""Settings page component."""

import os
from pathlib import Path
from typing import Callable, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gtk

from ui.domain.keyboard import KeyboardShortcut
from ui.infrastructure.gtk_keyboard_parser import GtkKeyboardParser
from ui.infrastructure.gsettings_store import GSettingsStore
from ui.services.shortcut_service import ShortcutService


class SettingsPage:
    def __init__(
        self,
        settings,
        on_save: Callable[[int, int, int], None],
        on_notification: Callable[[str], None],
    ):
        self.settings = settings
        self.on_save = on_save
        self.on_notification = on_notification
        self.item_width_spin = None
        self.item_height_spin = None
        self.page_length_spin = None

        # Shortcut service setup
        extension_dir = Path(__file__).parent.parent.parent / "gnome-extension"
        schema_dir = extension_dir / "schemas"
        self.settings_store = GSettingsStore(
            schema_id="org.gnome.shell.extensions.simple-clipboard",
            key="toggle-tfcbm-ui",
            schema_dir=schema_dir,
        )
        self.shortcut_service = ShortcutService(self.settings_store)
        self.keyboard_parser = GtkKeyboardParser()

        # Shortcut UI elements
        self.shortcut_display = None
        self.record_btn = None
        self.recording_status = None
        self.shortcut_recorder_window = None

    def build(self) -> Adw.PreferencesPage:
        settings_page = Adw.PreferencesPage()

        # General settings group (FIRST!)
        general_group = Adw.PreferencesGroup()
        general_group.set_title("General")
        general_group.set_description("General application settings")

        # Load on startup switch
        startup_row = Adw.SwitchRow()
        startup_row.set_title("Load on Startup")
        startup_row.set_subtitle("Automatically start TFCBM when you log in")
        startup_row.set_active(self._is_autostart_enabled())
        startup_row.connect("notify::active", self._on_autostart_toggled)
        general_group.add(startup_row)

        settings_page.add(general_group)

        # Keyboard shortcut group
        shortcut_group = self._build_shortcut_group()
        settings_page.add(shortcut_group)

        display_group = Adw.PreferencesGroup()
        display_group.set_title("Display Settings")
        display_group.set_description("Configure how clipboard items are displayed")

        item_width_row = Adw.SpinRow()
        item_width_row.set_title("Item Width")
        item_width_row.set_subtitle("Width of clipboard item cards in pixels (50-1000)")
        item_width_row.set_adjustment(
            Gtk.Adjustment.new(
                value=self.settings.item_width,
                lower=50,
                upper=1000,
                step_increment=10,
                page_increment=50,
                page_size=0,
            )
        )
        item_width_row.set_digits(0)
        self.item_width_spin = item_width_row
        display_group.add(item_width_row)

        item_height_row = Adw.SpinRow()
        item_height_row.set_title("Card height")
        item_height_row.set_subtitle(
            "Height of clipboard item cards in pixels (50-1000)"
        )
        item_height_row.set_adjustment(
            Gtk.Adjustment.new(
                value=self.settings.item_height,
                lower=50,
                upper=1000,
                step_increment=10,
                page_increment=50,
                page_size=0,
            )
        )
        item_height_row.set_digits(0)
        self.item_height_spin = item_height_row
        display_group.add(item_height_row)

        page_length_row = Adw.SpinRow()
        page_length_row.set_title("Max Page Length")
        page_length_row.set_subtitle("Maximum number of items to load per page (1-100)")
        page_length_row.set_adjustment(
            Gtk.Adjustment.new(
                value=self.settings.max_page_length,
                lower=1,
                upper=100,
                step_increment=1,
                page_increment=10,
                page_size=0,
            )
        )
        page_length_row.set_digits(0)
        self.page_length_spin = page_length_row
        display_group.add(page_length_row)

        settings_page.add(display_group)

        storage_group = Adw.PreferencesGroup()
        storage_group.set_title("Storage")
        storage_group.set_description("Database storage information")

        db_size_row = Adw.ActionRow()
        db_size_row.set_title("Database Size")

        db_path = Path.home() / ".local" / "share" / "tfcbm" / "clipboard.db"
        if db_path.exists():
            size_bytes = os.path.getsize(db_path)
            size_mb = size_bytes / (1024 * 1024)
            db_size_row.set_subtitle(f"{size_mb:.2f} MB")
        else:
            db_size_row.set_subtitle("Database not found")

        storage_group.add(db_size_row)
        settings_page.add(storage_group)

        actions_group = Adw.PreferencesGroup()
        actions_group.set_title("Actions")

        save_row = Adw.ActionRow()
        save_row.set_title("Save Settings")
        save_row.set_subtitle("Apply changes and save to settings.yml")

        save_button = Gtk.Button()
        save_button.set_label("Apply & Save")
        save_button.add_css_class("suggested-action")
        save_button.set_valign(Gtk.Align.CENTER)
        save_button.connect("clicked", self._on_save_clicked)
        save_row.add_suffix(save_button)

        actions_group.add(save_row)
        settings_page.add(actions_group)

        return settings_page

    def _on_save_clicked(self, button: Gtk.Button) -> None:
        try:
            new_item_width = int(self.item_width_spin.get_value())
            new_item_height = int(self.item_height_spin.get_value())
            new_page_length = int(self.page_length_spin.get_value())

            self.on_save(new_item_width, new_item_height, new_page_length)
            self.on_notification(
                "Settings saved successfully! Restart the app to apply changes."
            )

            print(
                f"Settings saved: item_width={new_item_width}, "
                f"item_height={new_item_height}, "
                f"max_page_length={new_page_length}"
            )

        except Exception as e:
            self.on_notification(f"Error saving settings: {str(e)}")
            print(f"Error saving settings: {e}")

    def _build_shortcut_group(self) -> Adw.PreferencesGroup:
        """Build the keyboard shortcut recorder section."""
        group = Adw.PreferencesGroup()
        group.set_title("Keyboard Shortcut")
        group.set_description("Configure the global keyboard shortcut to toggle TFCBM")

        # Current shortcut display row
        shortcut_row = Adw.ActionRow()
        shortcut_row.set_title("Current Shortcut")

        # Display current shortcut
        current = self.shortcut_service.get_current_shortcut()
        if current:
            display_text = current.to_display_string()
        else:
            display_text = "Ctrl+Escape (default)"

        self.shortcut_display = Gtk.Label()
        self.shortcut_display.set_markup(f"<b>{display_text}</b>")
        self.shortcut_display.set_valign(Gtk.Align.CENTER)
        shortcut_row.add_suffix(self.shortcut_display)

        group.add(shortcut_row)

        # Record new shortcut row
        record_row = Adw.ActionRow()
        record_row.set_title("Record New Shortcut")
        record_row.set_subtitle("Click to record, then press any key combination")

        self.record_btn = Gtk.Button()
        self.record_btn.set_label("Record")
        self.record_btn.add_css_class("suggested-action")
        self.record_btn.set_valign(Gtk.Align.CENTER)
        self.record_btn.connect("clicked", self._on_record_button_clicked)
        record_row.add_suffix(self.record_btn)

        group.add(record_row)

        # Recording status row
        status_row = Adw.ActionRow()
        status_row.set_title("")
        self.recording_status = Gtk.Label()
        self.recording_status.set_halign(Gtk.Align.START)
        self.recording_status.set_valign(Gtk.Align.CENTER)
        status_row.set_child(self.recording_status)
        group.add(status_row)

        # Register as observer
        self.shortcut_service.add_observer(self)

        return group

    def _on_record_button_clicked(self, button: Gtk.Button) -> None:
        """Handle record button click."""
        is_recording = self.shortcut_service.toggle_recording()

        if is_recording:
            self.record_btn.set_label("Stop Recording")
            self.record_btn.remove_css_class("suggested-action")
            self.record_btn.add_css_class("destructive-action")
            self.recording_status.set_markup("<i>Press any key combination...</i>")

            # Create and show a popup window to capture the key
            self._show_recording_popup()
        else:
            self.record_btn.set_label("Record")
            self.record_btn.remove_css_class("destructive-action")
            self.record_btn.add_css_class("suggested-action")
            self.recording_status.set_text("")
            if self.shortcut_recorder_window:
                self.shortcut_recorder_window.close()

    def _show_recording_popup(self) -> None:
        """Show a popup window to capture keyboard shortcut."""
        self.shortcut_recorder_window = Gtk.Window()
        self.shortcut_recorder_window.set_title("Recording Shortcut...")
        self.shortcut_recorder_window.set_default_size(400, 150)
        self.shortcut_recorder_window.set_modal(True)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        box.set_margin_top(30)
        box.set_margin_bottom(30)
        box.set_margin_start(30)
        box.set_margin_end(30)

        label = Gtk.Label()
        label.set_markup("<big><b>Press any key combination...</b></big>")
        box.append(label)

        instruction = Gtk.Label()
        instruction.set_text("The shortcut will be recorded automatically")
        instruction.add_css_class("dim-label")
        box.append(instruction)

        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda _: self._cancel_recording())
        cancel_btn.set_halign(Gtk.Align.CENTER)
        box.append(cancel_btn)

        self.shortcut_recorder_window.set_child(box)

        # Setup keyboard event handler
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self._on_key_pressed_in_popup)
        self.shortcut_recorder_window.add_controller(key_controller)

        self.shortcut_recorder_window.present()

    def _on_key_pressed_in_popup(
        self, controller: Gtk.EventControllerKey, keyval: int, keycode: int, state: int
    ) -> bool:
        """Handle key press in recording popup."""
        if not self.shortcut_service.is_recording:
            return False

        # Parse the key event
        event = self.keyboard_parser.parse_key_event(keyval, keycode, state)

        # Process it through the service
        shortcut = self.shortcut_service.process_key_event(event)

        if shortcut:
            # Apply it to the extension
            self.shortcut_service.apply_shortcut(shortcut)
            # Close the popup
            if self.shortcut_recorder_window:
                self.shortcut_recorder_window.close()
            return True

        return False

    def _cancel_recording(self) -> None:
        """Cancel the recording process."""
        self.shortcut_service.stop_recording()
        self.record_btn.set_label("Record")
        self.record_btn.remove_css_class("destructive-action")
        self.record_btn.add_css_class("suggested-action")
        self.recording_status.set_text("")
        if self.shortcut_recorder_window:
            self.shortcut_recorder_window.close()

    # ShortcutObserver implementations
    def on_shortcut_recorded(self, shortcut: KeyboardShortcut) -> None:
        """Called when a shortcut is recorded."""
        pass  # Handled in on_shortcut_applied

    def on_shortcut_applied(self, shortcut: KeyboardShortcut, success: bool) -> None:
        """Called when a shortcut application completes."""
        display_text = shortcut.to_display_string()

        if success:
            self.shortcut_display.set_markup(f"<b>{display_text}</b>")
            self.recording_status.set_markup(
                f"<span color='green'>✓ Applied: {display_text}</span>"
            )
            self.on_notification(
                f"Shortcut changed to {display_text}! The extension will use it immediately."
            )
        else:
            self.recording_status.set_markup(
                f"<span color='red'>✗ Failed to apply shortcut</span>"
            )
            self.on_notification(
                "Failed to apply shortcut. Make sure the extension is enabled."
            )

        # Reset button state
        self.record_btn.set_label("Record")
        self.record_btn.remove_css_class("destructive-action")
        self.record_btn.add_css_class("suggested-action")

    def _is_autostart_enabled(self) -> bool:
        """Check if autostart is enabled."""
        autostart_dir = Path.home() / ".config" / "autostart"
        autostart_file = autostart_dir / "tfcbm.desktop"
        return autostart_file.exists()

    def _on_autostart_toggled(self, switch_row, _param):
        """Handle autostart toggle."""
        is_enabled = switch_row.get_active()

        try:
            if is_enabled:
                self._enable_autostart()
                self.on_notification("TFCBM will now start automatically on login")
            else:
                self._disable_autostart()
                self.on_notification("TFCBM autostart disabled")
        except Exception as e:
            self.on_notification(f"Error toggling autostart: {e}")
            print(f"Error toggling autostart: {e}")

    def _enable_autostart(self):
        """Enable autostart by creating .desktop file in autostart directory."""
        autostart_dir = Path.home() / ".config" / "autostart"
        autostart_dir.mkdir(parents=True, exist_ok=True)

        autostart_file = autostart_dir / "tfcbm.desktop"

        # Get the installation directory
        install_dir = Path(__file__).parent.parent.parent
        launcher_script = install_dir / "tfcbm-launcher.sh"

        # Create the autostart desktop entry
        desktop_content = f"""[Desktop Entry]
Type=Application
Name=TFCBM
Comment=Clipboard Manager - Manage your clipboard history
Exec={launcher_script}
Icon={install_dir}/resouces/icon-256.png
Terminal=false
Categories=Utility;GTK;
StartupNotify=true
X-GNOME-Autostart-enabled=true
"""

        autostart_file.write_text(desktop_content)
        print(f"Autostart enabled: {autostart_file}")

    def _disable_autostart(self):
        """Disable autostart by removing the .desktop file."""
        autostart_file = Path.home() / ".config" / "autostart" / "tfcbm.desktop"

        if autostart_file.exists():
            autostart_file.unlink()
            print(f"Autostart disabled: {autostart_file}")
