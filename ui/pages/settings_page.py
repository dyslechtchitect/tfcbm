"""Settings page component."""

import os
from pathlib import Path
from typing import Callable, Optional

import gi

import logging

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, GObject, Gtk, Gio

logger = logging.getLogger("TFCBM.SettingsPage")

from ui.domain.keyboard import KeyboardShortcut
from ui.infrastructure.gtk_keyboard_parser import GtkKeyboardParser
from ui.infrastructure.gsettings_store import GSettingsStore
from ui.services.shortcut_service import ShortcutService


class SettingsPage:
    def __init__(
        self,
        settings,
        on_notification: Callable[[str], None],
        window=None,  # Optional window reference for direct communication
    ):
        self.settings = settings
        self.on_notification = on_notification
        self.window = window  # Store window reference for setting recording state

        # Shortcut service setup
        self.settings_store = GSettingsStore(
            schema_id="org.gnome.shell.extensions.tfcbm-clipboard-monitor",
            key="toggle-tfcbm-ui",
            schema_dir=None, # schema_dir is now handled by the extension via D-Bus, not loaded by the Flatpak app.
        )
        self.shortcut_service = ShortcutService(self.settings_store)
        self.keyboard_parser = GtkKeyboardParser()

        # Shortcut UI elements
        self.shortcut_display = None
        self.record_btn = None
        self.recording_status = None
        self.key_controller = None  # Store keyboard event controller
        self.parent_window = None  # Store reference to parent window

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

        # Extension management group
        extension_group = self._build_extension_group()
        settings_page.add(extension_group)

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
        from ui.services.ipc_helpers import connect as ipc_connect

        async def update_settings():
            try:
                async with ipc_connect() as conn:
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
            # No shortcut set - initialize with the default from schema
            display_text = "Ctrl+Escape (default)"
            logger.info("No shortcut configured, initializing with default: Ctrl+Escape")
            default_shortcut = KeyboardShortcut(modifiers=["Ctrl"], key="Escape")
            # Apply the default shortcut to ensure it's actually set in GSettings
            success = self.settings_store.set_shortcut(default_shortcut)
            if success:
                logger.info("Default shortcut initialized successfully")
                current = default_shortcut
            else:
                logger.warning("Failed to initialize default shortcut")

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
        try:
            logger.info("Record button clicked")
            is_recording = self.shortcut_service.toggle_recording()
            logger.info(f"Recording state toggled to: {is_recording}")

            if is_recording:
                self.record_btn.set_label("Stop Recording")
                self.record_btn.remove_css_class("suggested-action")
                self.record_btn.add_css_class("destructive-action")
                self.recording_status.set_markup("<i>Press any key combination...</i>")

                # Disable the global keybinding so we can capture it in the GTK window
                logger.info("Disabling global keybinding...")
                self.settings_store.disable_keybinding()

                # Attach keyboard controller to main window to capture shortcut
                logger.info("Attaching keyboard controller...")
                self._attach_keyboard_controller()
                logger.info("Setting recording state...")
                self._set_main_app_recording_state(True)
                logger.info("Record mode activated successfully")
            else:
                self.record_btn.set_label("Record")
                self.record_btn.remove_css_class("destructive-action")
                self.record_btn.add_css_class("suggested-action")
                self.recording_status.set_text("")

                # Remove keyboard controller when not recording
                logger.info("Detaching keyboard controller...")
                self._detach_keyboard_controller()
                logger.info("Clearing recording state...")
                self._set_main_app_recording_state(False)
                # Re-enable the global keybinding
                logger.info("Re-enabling global keybinding...")
                self.settings_store.enable_keybinding()
                logger.info("Record mode deactivated successfully")
        except Exception as e:
            logger.error(f"Error in record button click handler: {e}", exc_info=True)
            self.on_notification(f"Error: {str(e)}")

    def _attach_keyboard_controller(self) -> None:
        """Attach keyboard event controller to window for shortcut recording."""
        # Get the parent window
        if not self.parent_window:
            widget = self.record_btn
            while widget:
                widget = widget.get_parent()
                if isinstance(widget, Gtk.Window):
                    self.parent_window = widget
                    break

        if not self.parent_window:
            logger.error("Could not find parent window for keyboard controller")
            return

        # Create and attach keyboard controller
        self.key_controller = Gtk.EventControllerKey.new()
        self.key_controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        self.key_controller.connect("key-pressed", self._on_key_pressed_for_recording)
        self.parent_window.add_controller(self.key_controller)
        logger.debug("Attached keyboard controller to window")

    def _detach_keyboard_controller(self) -> None:
        """Remove keyboard event controller from window."""
        if self.key_controller and self.parent_window:
            self.parent_window.remove_controller(self.key_controller)
            self.key_controller = None
            logger.debug("Detached keyboard controller from window")

    def _on_key_pressed_for_recording(
        self, controller: Gtk.EventControllerKey, keyval: int, keycode: int, state: int
    ) -> bool:
        """Handle key press during shortcut recording (no popup)."""
        logger.info(f"🔑 Key pressed: keyval={keyval}, keycode={keycode}, state={state}, is_recording={self.shortcut_service.is_recording}")

        if not self.shortcut_service.is_recording:
            logger.warning("Key pressed but service not in recording mode!")
            return False

        try:
            # Parse the key event
            event = self.keyboard_parser.parse_key_event(keyval, keycode, state)
            logger.info(f"✅ Parsed event: {event}")

            # Process it through the service
            shortcut = self.shortcut_service.process_key_event(event)
            logger.info(f"✅ Processed shortcut: {shortcut}")

            if shortcut:
                # Apply it to the extension
                logger.info(f"🎯 Applying shortcut: {shortcut.to_display_string()}")
                self.shortcut_service.apply_shortcut(shortcut)
                # Note: Controller will be detached in on_shortcut_applied callback
                return True
            else:
                logger.info("⚠️ No shortcut generated (likely modifier-only)")

        except Exception as e:
            logger.error(f"❌ Error processing key event: {e}", exc_info=True)

        return False



    # ShortcutObserver implementations
    def on_shortcut_recorded(self, shortcut: KeyboardShortcut) -> None:
        """Called when a shortcut is recorded."""
        logger.info(f"📝 Shortcut recorded: {shortcut.to_display_string()}")
        pass  # Handled in on_shortcut_applied

    def on_shortcut_applied(self, shortcut: KeyboardShortcut, success: bool) -> None:
        """Called when a shortcut application completes."""
        logger.info(f"🔄 on_shortcut_applied callback: shortcut={shortcut.to_display_string()}, success={success}")
        display_text = shortcut.to_display_string()

        if success:
            self.shortcut_display.set_markup(f"<b>{display_text}</b>")
            self.recording_status.set_markup(
                f"<span color='green'>✓ Applied: {display_text}</span>"
            )
            self.on_notification(
                f"Shortcut changed to {display_text}! The extension will use it immediately."
            )
            logger.info(f"✅ Shortcut successfully applied: {display_text}")
        else:
            self.recording_status.set_markup(
                f"<span color='red'>✗ Failed to apply shortcut</span>"
            )
            self.on_notification(
                "Failed to apply shortcut. Make sure the extension is enabled."
            )
            logger.error(f"❌ Failed to apply shortcut: {display_text}")

        # Reset button state and detach controller
        self.record_btn.set_label("Record")
        self.record_btn.remove_css_class("destructive-action")
        self.record_btn.add_css_class("suggested-action")
        self._detach_keyboard_controller()
        # CRITICAL: Clear the recording flag so shortcuts work!
        self._set_main_app_recording_state(False)
        # Re-enable the global keybinding
        logger.info("Re-enabling global keybinding after shortcut applied...")
        self.settings_store.enable_keybinding()
        logger.info("🔚 Recording mode UI reset complete")

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
        from ui.services.ipc_helpers import connect as ipc_connect

        async def get_count():
            try:
                async with ipc_connect() as conn:
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
        from ui.services.ipc_helpers import connect as ipc_connect

        async def save_settings():
            try:
                async with ipc_connect() as conn:
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
        """Check if autostart is enabled via Background Portal."""
        try:
            bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            proxy = Gio.DBusProxy.new_sync(
                bus,
                Gio.DBusProxyFlags.NONE,
                None,
                "org.freedesktop.portal.Desktop",
                "/org/freedesktop/portal/desktop",
                "org.freedesktop.portal.Background",
                None
            )

            # Get the current autostart status
            # The portal stores this in GSettings, check if enabled
            app_id = self._get_installed_app_id()

            # Try to read the autostart status from portal settings
            # If RequestBackground was called with autostart=true, it should be enabled
            # For now, we'll fall back to checking the old autostart file
            # until we've set it via portal at least once
            autostart_file = Path.home() / ".config" / "autostart" / f"{app_id}.desktop"
            return autostart_file.exists()
        except Exception as e:
            logger.error(f"Error checking autostart status: {e}")
            return False

    def _set_autostart_via_portal(self, enable: bool):
        """Set autostart using Background Portal API."""
        try:
            bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            proxy = Gio.DBusProxy.new_sync(
                bus,
                Gio.DBusProxyFlags.NONE,
                None,
                "org.freedesktop.portal.Desktop",
                "/org/freedesktop/portal/desktop",
                "org.freedesktop.portal.Background",
                None
            )

            if enable:
                # Build options for RequestBackground
                options = GLib.Variant(
                    "a{sv}",
                    {
                        "reason": GLib.Variant("s", "TFCBM needs to run in the background to track clipboard history"),
                        "autostart": GLib.Variant("b", True),
                        "commandline": GLib.Variant("as", ["tfcbm", "--activate"]),
                        "dbus-activatable": GLib.Variant("b", False),
                    }
                )

                # Call RequestBackground
                # parent_window: empty string (no parent window handle)
                result = proxy.call_sync(
                    "RequestBackground",
                    GLib.Variant("(sa{sv})", ("", options)),
                    Gio.DBusCallFlags.NONE,
                    -1,  # timeout
                    None
                )

                logger.info(f"Background portal RequestBackground result: {result}")
                self.on_notification(
                    "Autostart enabled. TFCBM will start automatically on your next login."
                )
            else:
                # To disable autostart, we need to remove the autostart file
                # The portal doesn't provide a "disable" method, so we manually remove it
                app_id = self._get_installed_app_id()
                autostart_file = Path.home() / ".config" / "autostart" / f"{app_id}.desktop"
                if autostart_file.exists():
                    autostart_file.unlink()
                    self.on_notification("Autostart disabled successfully.")
                    logger.info(f"Removed autostart file: {autostart_file}")
                else:
                    self.on_notification("Autostart already disabled.")

        except GLib.Error as e:
            error_message = f"Error toggling autostart via portal: {e.message}"
            self.on_notification(f"Error: {error_message}")
            logger.error(error_message)
            raise
        except Exception as e:
            error_message = f"Error toggling autostart: {e}"
            self.on_notification(f"Error: {error_message}")
            logger.error(error_message)
            raise

    def _on_autostart_toggled(self, switch_row, _param):
        """Handle autostart toggle using Background Portal API."""
        is_enabled = switch_row.get_active()
        try:
            self._set_autostart_via_portal(is_enabled)
        except Exception:
            # If setting autostart fails, revert the switch state
            switch_row.set_active(not is_enabled)
            # Error message already handled by _set_autostart_via_portal

    def _build_extension_group(self) -> Adw.PreferencesGroup:
        """Build the extension management section."""
        group = Adw.PreferencesGroup()
        group.set_title("GNOME Extension")
        group.set_description("Manage the TFCBM GNOME Shell extension")

        # Extension status row
        from ui.utils.extension_check import get_extension_status
        status = get_extension_status()

        status_row = Adw.ActionRow()
        status_row.set_title("Extension Status")
        if status['ready']:
            status_row.set_subtitle("Installed and running")
        elif status['installed']:
            status_row.set_subtitle("Installed but not enabled")
        else:
            status_row.set_subtitle("Not installed")
        group.add(status_row)

        # Uninstall extension row
        uninstall_row = Adw.ActionRow()
        uninstall_row.set_title("Uninstall Extension")
        uninstall_row.set_subtitle("Remove the GNOME Shell extension before uninstalling the app")

        uninstall_button = Gtk.Button()
        uninstall_button.set_label("Uninstall")
        uninstall_button.add_css_class("destructive-action")
        uninstall_button.set_valign(Gtk.Align.CENTER)
        uninstall_button.connect("clicked", self._on_uninstall_extension_clicked)
        uninstall_button.set_sensitive(status['installed'])  # Only enable if installed
        uninstall_row.add_suffix(uninstall_button)

        group.add(uninstall_row)

        return group

    def _on_uninstall_extension_clicked(self, button: Gtk.Button):
        """Handle uninstall extension button click."""
        # Show confirmation dialog
        dialog = Adw.MessageDialog.new(
            None,
            "Uninstall GNOME Extension?",
            "This will disable and remove the TFCBM GNOME Shell extension. "
            "You should do this before uninstalling the app to ensure clean removal."
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("uninstall", "Uninstall Extension")
        dialog.set_response_appearance("uninstall", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        def on_response(dialog, response):
            if response == "uninstall":
                self._perform_extension_uninstall(button)
            dialog.close()

        dialog.connect("response", on_response)
        dialog.present()

    def _perform_extension_uninstall(self, button: Gtk.Button):
        """Actually perform the extension uninstall."""
        button.set_sensitive(False)
        button.set_label("Uninstalling...")

        import threading

        def uninstall_in_thread():
            from ui.utils.extension_check import uninstall_extension
            success, message = uninstall_extension()
            GLib.idle_add(self._handle_uninstall_result, success, message, button)

        thread = threading.Thread(target=uninstall_in_thread, daemon=True)
        thread.start()

    def _handle_uninstall_result(self, success: bool, message: str, button: Gtk.Button):
        """Handle extension uninstall result in GTK main thread."""
        if success:
            self.on_notification(f"✓ {message}")
            button.set_label("Uninstalled")
            # Keep button disabled since extension is now gone
        else:
            self.on_notification(f"Error: {message}")
            button.set_label("Uninstall")
            button.set_sensitive(True)

        return False  # Don't repeat idle_add

    def _get_installed_app_id(self):
        """Get the app ID."""
        return 'io.github.dyslechtchitect.tfcbm'

    def _set_main_app_recording_state(self, is_recording: bool):
        """Set the recording state directly on the window to prevent hiding during shortcut recording."""
        # Use parent_window if window not available (parent_window is found via widget traversal)
        target_window = self.window or self.parent_window

        if target_window:
            # Set flag directly on the window
            target_window.is_recording_shortcut = is_recording
            logger.info(f"Recording state set directly on window: {is_recording}")
        else:
            logger.warning("No window reference available to set recording state")

