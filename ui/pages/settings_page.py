"""Settings page component."""

import os
from pathlib import Path
from typing import Callable, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, GObject, Gtk

from ui.domain.keyboard import KeyboardShortcut
from ui.infrastructure.gtk_keyboard_parser import GtkKeyboardParser
from ui.infrastructure.gsettings_store import GSettingsStore
from ui.services.shortcut_service import ShortcutService


class SettingsPage:
    def __init__(
        self,
        settings,
        on_notification: Callable[[str], None],
    ):
        self.settings = settings
        self.on_notification = on_notification

        # Shortcut service setup
        # Look for the extension in the user's extensions directory
        extension_dir = Path.home() / ".local/share/gnome-shell/extensions/tfcbm-clipboard-monitor@github.com"
        schema_dir = extension_dir / "schemas"

        # Fall back to bundled extension if not installed
        if not schema_dir.exists():
            from ui.utils.extension_check import is_flatpak

            if is_flatpak():
                # In Flatpak, extension is bundled at /app/share/tfcbm/gnome-extension
                extension_dir = Path("/app/share/tfcbm/gnome-extension")
            else:
                # Regular install - extension is in project directory
                extension_dir = Path(__file__).parent.parent.parent / "gnome-extension"

            schema_dir = extension_dir / "schemas"

        self.settings_store = GSettingsStore(
            schema_id="org.gnome.shell.extensions.tfcbm-clipboard-monitor",
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
        startup_row.set_title("Start on Login")
        startup_row.set_subtitle("Automatically start TFCBM app and show tray icon when you log in")
        startup_row.set_active(self._is_autostart_enabled())
        startup_row.connect("notify::active", self._on_autostart_toggled)
        general_group.add(startup_row)

        settings_page.add(general_group)

        # Clipboard behavior group
        clipboard_group = self._build_clipboard_group()
        settings_page.add(clipboard_group)

        # Keyboard shortcut group
        shortcut_group = self._build_shortcut_group()
        settings_page.add(shortcut_group)

        # Retention settings group
        retention_group = self._build_retention_group()
        settings_page.add(retention_group)

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

        return settings_page

    def _build_clipboard_group(self) -> Adw.PreferencesGroup:
        """Build the clipboard behavior settings section."""
        group = Adw.PreferencesGroup()
        group.set_title("Clipboard Behavior")
        group.set_description("Configure keyboard selection behavior")

        # Refocus on copy switch
        refocus_row = Adw.SwitchRow()
        refocus_row.set_title("Refocus on Copy")
        refocus_row.set_subtitle(
            "Automatically hide window and refocus previous app when selecting via keyboard"
        )
        refocus_row.set_active(self.settings.refocus_on_copy)
        refocus_row.connect("notify::active", self._on_refocus_on_copy_toggled)
        group.add(refocus_row)

        return group

    def _on_refocus_on_copy_toggled(self, switch_row, _param):
        """Handle refocus on copy toggle."""
        is_enabled = switch_row.get_active()

        # Update via IPC in background thread
        import threading

        def update_in_thread():
            result = self._update_clipboard_settings_sync(is_enabled)
            GLib.idle_add(self._handle_clipboard_settings_result, result, is_enabled)

        thread = threading.Thread(target=update_in_thread, daemon=True)
        thread.start()

    def _update_clipboard_settings_sync(self, refocus_on_copy: bool) -> dict:
        """Update clipboard settings via IPC synchronously (runs in background thread)."""
        import asyncio
        import json
        from ui.services.ipc_helpers import websockets_compat as websockets, connect as ipc_connect

        async def update_settings():
            try:
                async with ipc_connect('ws://localhost:8765', ping_timeout=5) as conn:
                    request = {
                        "action": "update_clipboard_settings",
                        "refocus_on_copy": refocus_on_copy
                    }
                    await conn.send(json.dumps(request))
                    response = await conn.recv()
                    return json.loads(response)
            except Exception as e:
                print(f"Error updating clipboard settings: {e}")
                return {"status": "error", "message": str(e)}

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(update_settings())
        finally:
            loop.close()
        return result

    def _handle_clipboard_settings_result(self, result: dict, refocus_on_copy: bool):
        """Handle clipboard settings update result in GTK main thread."""
        if result.get("status") == "success":
            # Update local in-memory settings reference
            self.settings.settings.clipboard.refocus_on_copy = refocus_on_copy

            if refocus_on_copy:
                self.on_notification(
                    "Window will hide and refocus previous app when selecting via keyboard"
                )
            else:
                self.on_notification(
                    "Window will stay visible when selecting items via keyboard"
                )
        else:
            self.on_notification(f"Error updating setting: {result.get('message', 'Unknown error')}")
            print(f"Error updating refocus_on_copy: {result.get('message')}")

        return False  # Don't repeat idle_add

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
        # Create a simple modal window for better keyboard event capture
        window = Gtk.Window()
        window.set_title("Recording Shortcut...")
        window.set_modal(True)
        window.set_default_size(400, 150)

        # Create content box
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        # Add label
        label = Gtk.Label()
        label.set_markup("<big><b>Recording Shortcut...</b></big>\n\nPress any key combination.\nThe shortcut will be recorded automatically.")
        label.set_justify(Gtk.Justification.CENTER)
        box.append(label)

        # Add cancel button
        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.set_halign(Gtk.Align.CENTER)
        cancel_btn.connect("clicked", lambda _: self._cancel_recording_and_close_window())
        box.append(cancel_btn)

        window.set_child(box)

        # Setup keyboard event handler with capture phase for better event handling
        key_controller = Gtk.EventControllerKey.new()
        key_controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        key_controller.connect("key-pressed", self._on_key_pressed_in_popup)
        window.add_controller(key_controller)

        # Store reference to the window
        self.shortcut_recorder_window = window
        self.shortcut_recorder_window.present()

    def _on_key_pressed_in_popup(
        self, controller: Gtk.EventControllerKey, keyval: int, keycode: int, state: int
    ) -> bool:
        """Handle key press in recording popup."""
        print(f"[DEBUG] Key pressed in popup: keyval={keyval}, keycode={keycode}, state={state}, is_recording={self.shortcut_service.is_recording}")

        if not self.shortcut_service.is_recording:
            return False

        # Parse the key event
        event = self.keyboard_parser.parse_key_event(keyval, keycode, state)
        print(f"[DEBUG] Parsed event: {event}")

        # Process it through the service
        shortcut = self.shortcut_service.process_key_event(event)
        print(f"[DEBUG] Processed shortcut: {shortcut}")

        if shortcut:
            # Apply it to the extension
            print(f"[DEBUG] Applying shortcut: {shortcut.to_display_string()}")
            self.shortcut_service.apply_shortcut(shortcut)
            # Close the popup
            if self.shortcut_recorder_window:
                print("[DEBUG] Closing popup window")
                self.shortcut_recorder_window.close()
                self.shortcut_recorder_window = None
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
            self.shortcut_recorder_window = None

    def _cancel_recording_and_close_window(self) -> None:
        """Cancel recording and close the popup window."""
        self._cancel_recording()


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

    def _build_retention_group(self) -> Adw.PreferencesGroup:
        """Build the retention settings section."""
        group = Adw.PreferencesGroup()
        group.set_title("Item Retention")
        group.set_description("Automatically clean up old clipboard items")

        # Enable retention switch
        retention_switch = Adw.SwitchRow()
        retention_switch.set_title("Enable Automatic Cleanup")
        retention_switch.set_subtitle("Delete oldest items when limit is reached")
        retention_switch.set_active(self.settings.retention_enabled)
        retention_switch.connect("notify::active", self._on_retention_toggled)
        group.add(retention_switch)

        # Max items spinner
        max_items_row = Adw.SpinRow()
        max_items_row.set_title("Maximum Items")
        max_items_row.set_subtitle("Keep only this many recent items (10-10000)")
        max_items_row.set_adjustment(
            Gtk.Adjustment.new(
                value=self.settings.retention_max_items,
                lower=10,
                upper=10000,
                step_increment=10,
                page_increment=100,
                page_size=0,
            )
        )
        max_items_row.set_digits(0)
        max_items_row.connect("notify::value", self._on_max_items_changed)

        # Enable/disable based on retention switch
        max_items_row.set_sensitive(self.settings.retention_enabled)
        retention_switch.bind_property(
            "active",
            max_items_row,
            "sensitive",
            GObject.BindingFlags.SYNC_CREATE
        )

        self.retention_switch = retention_switch
        self.max_items_row = max_items_row
        group.add(max_items_row)

        # Apply button
        apply_row = Adw.ActionRow()
        apply_row.set_title("Apply Retention Settings")
        apply_row.set_subtitle("Save changes and apply cleanup if needed")

        apply_button = Gtk.Button()
        apply_button.set_label("Apply")
        apply_button.add_css_class("suggested-action")
        apply_button.set_valign(Gtk.Align.CENTER)
        apply_button.connect("clicked", self._on_apply_retention)
        apply_row.add_suffix(apply_button)

        group.add(apply_row)

        return group

    def _on_retention_toggled(self, switch_row, _param):
        """Handle retention toggle - just update in-memory setting."""
        # Setting will be saved when user confirms in the dialog
        pass

    def _on_max_items_changed(self, spin_row, _param):
        """Handle max items change - show confirmation if reducing."""
        new_value = int(spin_row.get_value())
        current_value = self.settings.retention_max_items

        if new_value < current_value:
            # User is reducing limit - will need confirmation
            # This will be handled by the save button
            pass

    def _on_apply_retention(self, button: Gtk.Button):
        """Handle retention settings apply button."""
        import threading

        new_enabled = self.retention_switch.get_active()
        new_max_items = int(self.max_items_row.get_value())
        current_max_items = self.settings.retention_max_items

        # Calculate if we need to delete items
        if new_enabled and new_max_items < current_max_items:
            # User is reducing the limit - show confirmation
            # First get item count in background thread
            def get_count_and_confirm():
                total = self._get_total_count_sync()
                GLib.idle_add(self._show_retention_confirmation_with_count, new_enabled, new_max_items, total)

            thread = threading.Thread(target=get_count_and_confirm, daemon=True)
            thread.start()
        else:
            # No deletion needed, just save
            self._save_retention_settings_threaded(new_enabled, new_max_items, delete_count=0)

    def _get_total_count_sync(self) -> int:
        """Get total item count synchronously (runs in background thread)."""
        import asyncio
        import json
        from ui.services.ipc_helpers import websockets_compat as websockets, connect as ipc_connect

        async def get_count():
            try:
                async with ipc_connect('ws://localhost:8765', ping_timeout=5) as conn:
                    await conn.send(json.dumps({"action": "get_total_count"}))
                    response = await conn.recv()
                    data = json.loads(response)
                    return data.get("total", 0)
            except Exception as e:
                print(f"Error getting item count: {e}")
                return 0

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            total = loop.run_until_complete(get_count())
        finally:
            loop.close()
        return total

    def _show_retention_confirmation_with_count(self, enabled: bool, max_items: int, total_items: int):
        """Show confirmation dialog with pre-calculated item count (runs in GTK main thread)."""
        items_to_delete = max(0, total_items - max_items)

        if items_to_delete == 0:
            # No items to delete
            self._save_retention_settings_threaded(enabled, max_items, delete_count=0)
            return False  # Don't repeat idle_add

        # Show confirmation dialog
        dialog = Adw.MessageDialog.new(
            None,  # parent window
            "Delete Old Items?",
            f"{items_to_delete} oldest items will be deleted to meet the new limit of {max_items} items."
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("delete", "Delete Items")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        def on_response(dialog, response):
            if response == "delete":
                self._save_retention_settings_threaded(enabled, max_items, delete_count=items_to_delete)
            dialog.close()

        dialog.connect("response", on_response)
        dialog.present()
        return False  # Don't repeat idle_add

    def _save_retention_settings_threaded(self, enabled: bool, max_items: int, delete_count: int):
        """Save retention settings in background thread to avoid UI freeze."""
        import threading

        def save_in_thread():
            result = self._save_retention_settings_sync(enabled, max_items, delete_count)
            # Update UI in main thread
            GLib.idle_add(self._handle_retention_save_result, result, enabled, max_items)

        thread = threading.Thread(target=save_in_thread, daemon=True)
        thread.start()

    def _save_retention_settings_sync(self, enabled: bool, max_items: int, delete_count: int) -> dict:
        """Save retention settings synchronously (runs in background thread)."""
        import asyncio
        import json
        from ui.services.ipc_helpers import websockets_compat as websockets, connect as ipc_connect

        async def save_settings():
            try:
                async with ipc_connect('ws://localhost:8765', ping_timeout=10) as conn:
                    request = {
                        "action": "update_retention_settings",
                        "enabled": enabled,
                        "max_items": max_items,
                        "delete_count": delete_count
                    }
                    await conn.send(json.dumps(request))
                    response = await conn.recv()
                    return json.loads(response)
            except Exception as e:
                print(f"Error saving retention settings: {e}")
                return {"status": "error", "message": str(e)}

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(save_settings())
        finally:
            loop.close()
        return result

    def _handle_retention_save_result(self, result: dict, enabled: bool, max_items: int):
        """Handle save result in GTK main thread."""
        if result.get("status") == "success":
            # Update local in-memory settings reference
            # Note: The backend already saved to file via IPC handler
            self.settings.settings.retention.enabled = enabled
            self.settings.settings.retention.max_items = max_items

            deleted = result.get("deleted", 0)
            if deleted > 0:
                self.on_notification(
                    f"Retention settings applied! {deleted} old items deleted."
                )
            else:
                self.on_notification("Retention settings applied successfully!")
        else:
            self.on_notification(f"Error: {result.get('message', 'Unknown error')}")

        return False  # Don't repeat idle_add

    def _is_autostart_enabled(self) -> bool:
        """Check if autostart is enabled by reading the XDG autostart desktop file."""
        autostart_dir = Path.home() / ".config" / "autostart"
        autostart_file = autostart_dir / "io.github.dyslechtchitect.tfcbm.desktop"

        if not autostart_file.exists():
            return False

        # Check if the desktop entry is enabled (not hidden or disabled)
        return self._is_desktop_entry_enabled(autostart_file)

    def _is_desktop_entry_enabled(self, desktop_file: Path) -> bool:
        """Check if a desktop entry is enabled (not hidden or disabled)."""
        try:
            content = desktop_file.read_text()

            # XDG standard check - Hidden=true means disabled
            if "Hidden=true" in content:
                return False

            # GNOME-specific check
            if "X-GNOME-Autostart-enabled=false" in content:
                return False

            return True
        except Exception as e:
            print(f"Error reading desktop file: {e}")
            return False

    def _on_autostart_toggled(self, switch_row, _param):
        """Handle autostart toggle - only affects next login, not current session."""
        is_enabled = switch_row.get_active()

        try:
            if is_enabled:
                self._enable_autostart()
                self.on_notification("TFCBM will start automatically when you log in")
            else:
                self._disable_autostart()
                self.on_notification("TFCBM will not start automatically when you log in")
        except Exception as e:
            self.on_notification(f"Error toggling autostart: {e}")
            print(f"Error toggling autostart: {e}")

    def _get_installed_app_id(self):
        """Get the app ID."""
        return 'io.github.dyslechtchitect.tfcbm'

    def _enable_autostart(self):
        """Enable autostart by creating/updating .desktop file in ~/.config/autostart."""
        from ui.utils.extension_check import is_flatpak

        autostart_dir = Path.home() / ".config" / "autostart"
        autostart_dir.mkdir(parents=True, exist_ok=True)

        # Detect which app ID is installed
        app_id = self._get_installed_app_id()
        autostart_file = autostart_dir / f"{app_id}.desktop"

        # Determine the correct Exec command
        # NOTE: Autostart should NOT include --activate flag, so app runs in background
        # with just the tray icon. Window can be shown via keyboard shortcut or tray icon.
        if is_flatpak():
            exec_cmd = f"flatpak run {app_id}"
        else:
            # For non-Flatpak, use the installed binary
            exec_cmd = "tfcbm"

        # Create the autostart desktop entry following XDG and GNOME standards
        # Note: We explicitly set X-GNOME-Autostart-enabled=true and ensure
        # Hidden is NOT present (or explicitly false)
        desktop_content = f"""[Desktop Entry]
Type=Application
Name=TFCBM
Comment=The F* Clipboard Manager
Exec={exec_cmd}
Icon={app_id}
Terminal=false
Categories=Utility;GTK;
StartupNotify=false
X-GNOME-Autostart-enabled=true
"""

        autostart_file.write_text(desktop_content)
        print(f"Autostart enabled: {autostart_file}")

    def _disable_autostart(self):
        """Disable autostart by setting Hidden=true and X-GNOME-Autostart-enabled=false.

        Following XDG Desktop Entry Specification, we don't delete the file but mark it
        as hidden/disabled. This allows GNOME Settings to re-enable it if needed and
        maintains proper sync with the system settings UI.
        """
        from ui.utils.extension_check import is_flatpak

        autostart_dir = Path.home() / ".config" / "autostart"
        autostart_file = autostart_dir / "io.github.dyslechtchitect.tfcbm.desktop"

        if not autostart_file.exists():
            # Need to create the file first, then mark it as disabled
            self._enable_autostart()

        # Read current content
        try:
            content = autostart_file.read_text()

            # Check if already disabled
            if "Hidden=true" in content and "X-GNOME-Autostart-enabled=false" in content:
                print(f"Autostart already disabled: {autostart_file}")
                return

            # Remove any existing Hidden or X-GNOME-Autostart-enabled lines
            lines = content.split('\n')
            filtered_lines = [
                line for line in lines
                if not line.startswith('Hidden=')
                and not line.startswith('X-GNOME-Autostart-enabled=')
            ]

            # Add the disable flags after [Desktop Entry]
            new_lines = []
            for line in filtered_lines:
                new_lines.append(line)
                if line.strip() == '[Desktop Entry]':
                    new_lines.append('Hidden=true')
                    new_lines.append('X-GNOME-Autostart-enabled=false')

            # Write back
            autostart_file.write_text('\n'.join(new_lines))
            print(f"Autostart disabled: set Hidden=true in {autostart_file}")

        except Exception as e:
            print(f"Error disabling autostart: {e}")
            raise
