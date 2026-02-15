"""Settings page component - DE-agnostic GTK4 version."""

import os
from pathlib import Path
from typing import Callable, Optional

import gi

import logging

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, GLib, GObject, Gtk, Gio

logger = logging.getLogger("TFCBM.SettingsPage")

from ui.domain.keyboard import KeyboardShortcut
from ui.infrastructure.gtk_keyboard_parser import GtkKeyboardParser
from ui.infrastructure.json_settings_store import JsonSettingsStore
from ui.services.shortcut_service import ShortcutService
from ui.utils.color_utils import sanitize_color, hex_to_rgba


def _create_settings_row(title, subtitle=None):
    """Create a GTK4 ListBoxRow that mimics Adw.ActionRow layout."""
    row = Gtk.ListBoxRow()
    row.set_activatable(False)

    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    box.set_margin_top(8)
    box.set_margin_bottom(8)
    box.set_margin_start(12)
    box.set_margin_end(12)

    text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    text_box.set_hexpand(True)
    text_box.set_valign(Gtk.Align.CENTER)

    title_label = Gtk.Label(label=title)
    title_label.set_halign(Gtk.Align.START)
    title_label.set_wrap(True)
    text_box.append(title_label)

    if subtitle:
        sub_label = Gtk.Label(label=subtitle)
        sub_label.set_halign(Gtk.Align.START)
        sub_label.add_css_class("dim-label")
        sub_label.add_css_class("caption")
        sub_label.set_wrap(True)
        text_box.append(sub_label)

    box.append(text_box)
    row.set_child(box)
    return row, box


def _create_settings_group(title, description=None):
    """Create a settings group (Frame with ListBox) mimicking Adw.PreferencesGroup."""
    frame = Gtk.Frame()
    frame.set_margin_start(12)
    frame.set_margin_end(12)
    frame.set_margin_top(8)
    frame.set_margin_bottom(8)

    outer_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)

    # Group title
    title_label = Gtk.Label()
    title_label.set_markup(f"<b>{title}</b>")
    title_label.set_halign(Gtk.Align.START)
    title_label.set_margin_start(4)
    title_label.set_margin_top(4)
    outer_box.append(title_label)

    if description:
        desc_label = Gtk.Label(label=description)
        desc_label.set_halign(Gtk.Align.START)
        desc_label.set_margin_start(4)
        desc_label.add_css_class("dim-label")
        desc_label.add_css_class("caption")
        desc_label.set_wrap(True)
        outer_box.append(desc_label)

    listbox = Gtk.ListBox()
    listbox.add_css_class("boxed-list")
    listbox.set_selection_mode(Gtk.SelectionMode.NONE)
    outer_box.append(listbox)

    frame.set_child(outer_box)
    return frame, listbox


class SettingsPage:
    def __init__(
        self,
        settings,
        on_notification: Callable[[str], None],
        window=None,
    ):
        self.settings = settings
        self.on_notification = on_notification
        self.window = window

        # Shortcut service setup - using JSON settings store (DE-agnostic)
        self.settings_store = JsonSettingsStore()
        self.shortcut_service = ShortcutService(self.settings_store)
        self.keyboard_parser = GtkKeyboardParser()

        # Shortcut UI elements
        self.shortcut_display = None
        self.record_btn = None
        self.recording_status = None
        self.key_controller = None
        self.parent_window = None

    def build(self) -> Gtk.ScrolledWindow:
        """Build the settings page using pure GTK4 widgets."""
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)

        page_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        page_box.set_margin_top(8)
        page_box.set_margin_bottom(8)

        # General settings group
        general_frame, general_list = _create_settings_group(
            "General", "General application settings"
        )

        startup_row, startup_box = _create_settings_row(
            "Start on Login",
            "Automatically start TFCBM app when you log in"
        )
        self.startup_switch = Gtk.Switch()
        self.startup_switch.set_active(self._is_autostart_enabled())
        self.startup_switch.set_valign(Gtk.Align.CENTER)
        self._autostart_handler_id = self.startup_switch.connect("notify::active", self._on_autostart_toggled)
        startup_box.append(self.startup_switch)
        general_list.append(startup_row)

        page_box.append(general_frame)

        # Clipboard behavior group
        clipboard_frame, clipboard_list = self._build_clipboard_group()
        page_box.append(clipboard_frame)

        # Keyboard shortcut group
        shortcut_frame, shortcut_list = self._build_shortcut_group()
        page_box.append(shortcut_frame)

        # Retention settings group
        retention_frame, retention_list = self._build_retention_group()
        page_box.append(retention_frame)

        # Storage group
        storage_frame, storage_list = _create_settings_group(
            "Storage", "Database storage information"
        )

        from ui.config import AppPaths
        db_path = AppPaths.default().db_path
        if db_path.exists():
            size_bytes = os.path.getsize(db_path)
            if size_bytes == 0:
                size_str = "Empty (0 bytes)"
            elif size_bytes < 1024:
                size_str = f"{size_bytes} bytes"
            elif size_bytes < 1024 * 1024:
                size_kb = size_bytes / 1024
                size_str = f"{size_kb:.2f} KB"
            else:
                size_mb = size_bytes / (1024 * 1024)
                size_str = f"{size_mb:.2f} MB"
        else:
            size_str = "Database not found"

        db_row, db_box = _create_settings_row("Database Size", size_str)
        storage_list.append(db_row)
        page_box.append(storage_frame)

        # Theme group
        theme_frame = self._build_theme_group()
        page_box.append(theme_frame)

        scrolled.set_child(page_box)
        return scrolled

    THEME_COLORS = [
        "#3584e4",  # Blue
        "#33d17a",  # Green
        "#f6d32d",  # Yellow
        "#ff7800",  # Orange
        "#e01b24",  # Red
        "#9141ac",  # Purple
        "#986a44",  # Brown
        "#5e5c64",  # Gray
        "#ff69b4",  # Pink
        "#7fff00",  # Chartreuse
    ]

    def _build_theme_group(self):
        """Build the theme settings section with color picker and transparency controls."""
        frame, listbox = _create_settings_group(
            "Theme", "Customize window appearance"
        )

        theme = self.settings_store.get_theme()
        current_color = theme.get('background_color')

        # Row 1: Background Color
        color_row = Gtk.ListBoxRow()
        color_row.set_activatable(False)
        color_outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        color_outer.set_margin_top(8)
        color_outer.set_margin_bottom(8)
        color_outer.set_margin_start(12)
        color_outer.set_margin_end(12)

        color_label = Gtk.Label(label="Background Color")
        color_label.set_halign(Gtk.Align.START)
        color_outer.append(color_label)

        color_flow = Gtk.FlowBox()
        color_flow.set_selection_mode(Gtk.SelectionMode.SINGLE)
        color_flow.set_max_children_per_line(11)
        color_flow.set_column_spacing(6)
        color_flow.set_row_spacing(6)
        color_flow.set_homogeneous(True)

        # "Default" button (no tint)
        default_btn = Gtk.Button()
        default_btn.set_size_request(36, 36)
        default_btn.set_label("X")
        default_btn.set_tooltip_text("Default (no tint)")
        default_btn.color_value = None
        default_css = Gtk.CssProvider()
        default_css.load_from_string(
            "button { background-color: #9a9996; background-image: none;"
            " border-radius: 18px; border: none; box-shadow: none;"
            " min-width: 36px; min-height: 36px; padding: 0;"
            " font-weight: bold; color: white; }"
        )
        default_btn.get_style_context().add_provider(
            default_css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        def on_default_click(btn, flow=color_flow):
            parent = btn.get_parent()
            if parent:
                flow.select_child(parent)

        default_btn.connect("clicked", on_default_click)
        color_flow.append(default_btn)

        # Color buttons
        for color in self.THEME_COLORS:
            color_btn = Gtk.Button()
            color_btn.set_size_request(36, 36)
            color_clean = sanitize_color(color)
            color_btn.color_value = color_clean
            css_provider = Gtk.CssProvider()
            css_provider.load_from_string(
                f"button {{ background-color: {color_clean}; background-image: none;"
                f" border-radius: 18px; border: none; box-shadow: none;"
                f" min-width: 36px; min-height: 36px; padding: 0; }}"
            )
            color_btn.get_style_context().add_provider(
                css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

            def on_color_click(btn, flow=color_flow):
                parent = btn.get_parent()
                if parent:
                    flow.select_child(parent)

            color_btn.connect("clicked", on_color_click)
            color_flow.append(color_btn)

        # Select the current color
        select_index = 0  # Default button at index 0
        if current_color:
            for i, c in enumerate(self.THEME_COLORS):
                if sanitize_color(c) == current_color:
                    select_index = i + 1  # +1 because default is at 0
                    break

        def select_initial_color():
            child = color_flow.get_child_at_index(select_index)
            if child:
                color_flow.select_child(child)
            return False

        GLib.idle_add(select_initial_color)

        color_flow.connect("selected-children-changed", self._on_theme_color_changed)
        self._theme_color_flow = color_flow

        color_outer.append(color_flow)
        color_row.set_child(color_outer)
        listbox.append(color_row)

        # Row 2: Transparency toggle
        transparency_row, transparency_box = _create_settings_row(
            "Enable Transparency",
            "Make the window semi-transparent (requires compositor)"
        )
        self._transparency_switch = Gtk.Switch()
        self._transparency_switch.set_active(theme.get('transparency_enabled', False))
        self._transparency_switch.set_valign(Gtk.Align.CENTER)
        self._transparency_switch.connect("notify::active", self._on_transparency_toggled)
        transparency_box.append(self._transparency_switch)
        listbox.append(transparency_row)

        # Row 3: Opacity slider
        opacity_row, opacity_box = _create_settings_row(
            "Window Opacity",
            "Adjust transparency level (30% – 100%)"
        )
        adjustment = Gtk.Adjustment.new(
            value=theme.get('transparency_level', 0.9),
            lower=0.3,
            upper=1.0,
            step_increment=0.05,
            page_increment=0.1,
            page_size=0,
        )
        self._opacity_scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL)
        self._opacity_scale.set_adjustment(adjustment)
        self._opacity_scale.set_draw_value(True)
        self._opacity_scale.set_digits(2)
        self._opacity_scale.set_hexpand(True)
        self._opacity_scale.set_size_request(150, -1)
        self._opacity_scale.set_sensitive(theme.get('transparency_enabled', False))
        self._opacity_scale.connect("value-changed", self._on_opacity_changed)
        opacity_box.append(self._opacity_scale)
        listbox.append(opacity_row)

        return frame

    def _on_theme_color_changed(self, flow):
        """Handle color selection change — apply color only, don't touch transparency."""
        selected = flow.get_selected_children()
        if not selected:
            return

        child = selected[0]
        btn = child.get_child()
        color = getattr(btn, 'color_value', None)

        theme = self.settings_store.get_theme()
        theme['background_color'] = color
        self.settings_store.set_theme(theme)

        if self.window:
            self.window.apply_theme_color(color)

    def _on_transparency_toggled(self, switch, _param):
        """Handle transparency toggle — apply opacity only, don't touch color."""
        enabled = switch.get_active()
        self._opacity_scale.set_sensitive(enabled)

        theme = self.settings_store.get_theme()
        theme['transparency_enabled'] = enabled
        self.settings_store.set_theme(theme)

        if self.window:
            level = theme.get('transparency_level', 0.9)
            self.window.apply_theme_opacity(enabled, level)

    def _on_opacity_changed(self, scale):
        """Handle opacity slider change — live preview, debounced save."""
        level = scale.get_value()

        # Live preview: set opacity directly (cheap, no file I/O)
        if self.window:
            self.window.set_opacity(max(0.3, min(1.0, level)))

        # Debounce the file save — cancel previous pending save
        if hasattr(self, '_opacity_save_timeout') and self._opacity_save_timeout:
            GLib.source_remove(self._opacity_save_timeout)

        def save_opacity():
            theme = self.settings_store.get_theme()
            theme['transparency_level'] = round(level, 2)
            self.settings_store.set_theme(theme)
            self._opacity_save_timeout = None
            return False

        self._opacity_save_timeout = GLib.timeout_add(300, save_opacity)

    def _build_clipboard_group(self):
        """Build the clipboard behavior settings section."""
        frame, listbox = _create_settings_group(
            "Clipboard Behavior", "Configure keyboard selection behavior"
        )

        row, box = _create_settings_row(
            "Refocus on Copy",
            "Automatically hide window and refocus previous app when selecting via keyboard"
        )
        refocus_switch = Gtk.Switch()
        refocus_switch.set_active(self.settings.refocus_on_copy)
        refocus_switch.set_valign(Gtk.Align.CENTER)
        refocus_switch.connect("notify::active", self._on_refocus_on_copy_toggled)
        box.append(refocus_switch)
        listbox.append(row)

        return frame, listbox

    def _on_refocus_on_copy_toggled(self, switch, _param):
        """Handle refocus on copy toggle."""
        is_enabled = switch.get_active()

        import threading

        def update_in_thread():
            result = self._update_clipboard_settings_sync(is_enabled)
            GLib.idle_add(self._handle_clipboard_settings_result, result, is_enabled)

        thread = threading.Thread(target=update_in_thread, daemon=True)
        thread.start()

    def _update_clipboard_settings_sync(self, refocus_on_copy: bool) -> dict:
        """Update clipboard settings via IPC synchronously."""
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

        return False

    def _build_shortcut_group(self):
        """Build the keyboard shortcut recorder section."""
        frame, listbox = _create_settings_group(
            "Keyboard Shortcut", "Configure the global keyboard shortcut to toggle TFCBM"
        )

        # Current shortcut display row
        row, box = _create_settings_row("Current Shortcut")

        current = self.shortcut_service.get_current_shortcut()
        if current:
            display_text = current.to_display_string()
        else:
            display_text = "Ctrl+Escape (default)"
            logger.info("No shortcut configured, initializing with default: Ctrl+Escape")
            default_shortcut = KeyboardShortcut(modifiers=["Ctrl"], key="Escape")
            success = self.settings_store.set_shortcut(default_shortcut)
            if success:
                current = default_shortcut

        self.shortcut_display = Gtk.Label()
        self.shortcut_display.set_markup(f"<b>{display_text}</b>")
        self.shortcut_display.set_valign(Gtk.Align.CENTER)
        box.append(self.shortcut_display)
        listbox.append(row)

        # Record new shortcut row
        record_row, record_box = _create_settings_row(
            "Record New Shortcut", "Click to record, then press any key combination"
        )
        self.record_btn = Gtk.Button()
        self.record_btn.set_label("Record")
        self.record_btn.add_css_class("suggested-action")
        self.record_btn.set_valign(Gtk.Align.CENTER)
        self.record_btn.connect("clicked", self._on_record_button_clicked)
        record_box.append(self.record_btn)
        listbox.append(record_row)

        # Recording status row
        status_row, status_box = _create_settings_row("")
        self.recording_status = Gtk.Label()
        self.recording_status.set_halign(Gtk.Align.START)
        self.recording_status.set_valign(Gtk.Align.CENTER)
        status_box.append(self.recording_status)
        listbox.append(status_row)

        # Register as observer
        self.shortcut_service.add_observer(self)

        return frame, listbox

    def _on_record_button_clicked(self, button: Gtk.Button) -> None:
        """Handle record button click."""
        try:
            logger.info("Record button clicked")
            is_recording = self.shortcut_service.toggle_recording()

            if is_recording:
                self.record_btn.set_label("Stop Recording")
                self.record_btn.remove_css_class("suggested-action")
                self.record_btn.add_css_class("destructive-action")
                self.recording_status.set_markup("<i>Press any key combination...</i>")

                self._set_shortcut_listener_enabled(False)

                self._attach_keyboard_controller()
                self._set_main_app_recording_state(True)
            else:
                self.record_btn.set_label("Record")
                self.record_btn.remove_css_class("destructive-action")
                self.record_btn.add_css_class("suggested-action")
                self.recording_status.set_text("")

                self._detach_keyboard_controller()
                self._set_main_app_recording_state(False)
                self._set_shortcut_listener_enabled(True)
        except Exception as e:
            logger.error(f"Error in record button click handler: {e}", exc_info=True)
            self.on_notification(f"Error: {str(e)}")

    def _attach_keyboard_controller(self) -> None:
        """Attach keyboard event controller to window for shortcut recording."""
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

        self.key_controller = Gtk.EventControllerKey.new()
        self.key_controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        self.key_controller.connect("key-pressed", self._on_key_pressed_for_recording)
        self.parent_window.add_controller(self.key_controller)

    def _detach_keyboard_controller(self) -> None:
        """Remove keyboard event controller from window."""
        if self.key_controller and self.parent_window:
            self.parent_window.remove_controller(self.key_controller)
            self.key_controller = None

    def _on_key_pressed_for_recording(
        self, controller: Gtk.EventControllerKey, keyval: int, keycode: int, state: int
    ) -> bool:
        """Handle key press during shortcut recording."""
        if not self.shortcut_service.is_recording:
            return False

        try:
            event = self.keyboard_parser.parse_key_event(keyval, keycode, state)
            shortcut = self.shortcut_service.process_key_event(event)

            if shortcut:
                logger.info(f"Applying shortcut: {shortcut.to_display_string()}")
                self.shortcut_service.apply_shortcut(shortcut)
                return True
        except Exception as e:
            logger.error(f"Error processing key event: {e}", exc_info=True)

        return False

    # ShortcutObserver implementations
    def on_shortcut_recorded(self, shortcut: KeyboardShortcut) -> None:
        """Called when a shortcut is recorded."""
        pass

    def on_shortcut_applied(self, shortcut: KeyboardShortcut, success: bool) -> None:
        """Called when a shortcut application completes."""
        display_text = shortcut.to_display_string()

        if success:
            self.shortcut_display.set_markup(f"<b>{display_text}</b>")
            self.recording_status.set_markup(
                f"<span color='green'>Applied: {display_text}</span>"
            )
            self.on_notification(f"Shortcut changed to {display_text}!")
        else:
            self.recording_status.set_markup(
                f"<span color='red'>Failed to apply shortcut</span>"
            )
            self.on_notification("Failed to apply shortcut.")

        self.record_btn.set_label("Record")
        self.record_btn.remove_css_class("destructive-action")
        self.record_btn.add_css_class("suggested-action")
        self._detach_keyboard_controller()
        self._set_main_app_recording_state(False)
        self._set_shortcut_listener_enabled(True)

    def _build_retention_group(self):
        """Build the retention settings section."""
        frame, listbox = _create_settings_group(
            "Item Retention", "Automatically clean up old clipboard items"
        )

        # Enable retention switch
        retention_row, retention_box = _create_settings_row(
            "Enable Automatic Cleanup",
            "Delete oldest items when limit is reached"
        )
        self.retention_switch = Gtk.Switch()
        self.retention_switch.set_active(self.settings.retention_enabled)
        self.retention_switch.set_valign(Gtk.Align.CENTER)
        retention_box.append(self.retention_switch)
        listbox.append(retention_row)

        # Max items spinner
        max_items_row, max_items_box = _create_settings_row(
            "Maximum Items", "Keep only this many recent items (10-10000)"
        )
        adjustment = Gtk.Adjustment.new(
            value=self.settings.retention_max_items,
            lower=10,
            upper=10000,
            step_increment=10,
            page_increment=100,
            page_size=0,
        )
        self.max_items_spin = Gtk.SpinButton()
        self.max_items_spin.set_adjustment(adjustment)
        self.max_items_spin.set_digits(0)
        self.max_items_spin.set_valign(Gtk.Align.CENTER)
        self.max_items_spin.set_sensitive(self.settings.retention_enabled)

        # Bind sensitivity to retention switch
        self.retention_switch.connect("notify::active",
            lambda sw, _: self.max_items_spin.set_sensitive(sw.get_active()))

        max_items_box.append(self.max_items_spin)
        listbox.append(max_items_row)

        # Apply button
        apply_row, apply_box = _create_settings_row(
            "Apply Retention Settings",
            "Save changes and apply cleanup if needed"
        )
        apply_button = Gtk.Button()
        apply_button.set_label("Apply")
        apply_button.add_css_class("suggested-action")
        apply_button.set_valign(Gtk.Align.CENTER)
        apply_button.connect("clicked", self._on_apply_retention)
        apply_box.append(apply_button)
        listbox.append(apply_row)

        return frame, listbox

    def _on_apply_retention(self, button: Gtk.Button):
        """Handle retention settings apply button."""
        import threading

        new_enabled = self.retention_switch.get_active()
        new_max_items = int(self.max_items_spin.get_value())
        current_max_items = self.settings.retention_max_items

        if new_enabled and new_max_items < current_max_items:
            def get_count_and_confirm():
                total = self._get_total_count_sync()
                GLib.idle_add(self._show_retention_confirmation_with_count, new_enabled, new_max_items, total)

            thread = threading.Thread(target=get_count_and_confirm, daemon=True)
            thread.start()
        else:
            self._save_retention_settings_threaded(new_enabled, new_max_items, delete_count=0)

    def _get_total_count_sync(self) -> int:
        """Get total item count synchronously."""
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
        """Show confirmation dialog with pre-calculated item count."""
        items_to_delete = max(0, total_items - max_items)

        if items_to_delete == 0:
            self._save_retention_settings_threaded(enabled, max_items, delete_count=0)
            return False

        # Find parent window
        parent = self.window
        if not parent and self.parent_window:
            parent = self.parent_window

        dialog = Gtk.MessageDialog(
            transient_for=parent,
            modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.NONE,
            text="Delete Old Items?",
            secondary_text=f"{items_to_delete} oldest items will be deleted to meet the new limit of {max_items} items.",
        )
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        delete_btn = dialog.add_button("Delete Items", Gtk.ResponseType.OK)
        delete_btn.add_css_class("destructive-action")

        def on_response(dialog, response_id):
            if response_id == Gtk.ResponseType.OK:
                self._save_retention_settings_threaded(enabled, max_items, delete_count=items_to_delete)
            dialog.destroy()

        dialog.connect("response", on_response)
        dialog.present()
        return False

    def _save_retention_settings_threaded(self, enabled: bool, max_items: int, delete_count: int):
        """Save retention settings in background thread."""
        import threading

        def save_in_thread():
            result = self._save_retention_settings_sync(enabled, max_items, delete_count)
            GLib.idle_add(self._handle_retention_save_result, result, enabled, max_items)

        thread = threading.Thread(target=save_in_thread, daemon=True)
        thread.start()

    def _save_retention_settings_sync(self, enabled: bool, max_items: int, delete_count: int) -> dict:
        """Save retention settings synchronously."""
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

        return False

    def _is_autostart_enabled(self) -> bool:
        """Check if autostart is enabled from app settings."""
        return self.settings.autostart_enabled

    def _is_background_portal_available(self) -> bool:
        """Check if the Background portal interface is available."""
        try:
            bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            proxy = Gio.DBusProxy.new_sync(
                bus,
                Gio.DBusProxyFlags.DO_NOT_AUTO_START,
                None,
                "org.freedesktop.portal.Desktop",
                "/org/freedesktop/portal/desktop",
                "org.freedesktop.DBus.Introspectable",
                None
            )
            xml = proxy.call_sync("Introspect", None, Gio.DBusCallFlags.NONE, 1000, None)
            introspection = xml.unpack()[0] if xml else ""
            return "org.freedesktop.portal.Background" in introspection
        except Exception as e:
            logger.debug(f"Could not introspect portal: {e}")
            return False

    def _set_autostart_via_portal(self, enable: bool):
        """Set autostart using Background Portal API."""
        logger.info(f"Starting autostart portal call: enable={enable}")

        # Check if portal interface exists first
        if not self._is_background_portal_available():
            logger.info("Background portal not available on this system")
            return False

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

            try:
                app_id = self._get_installed_app_id()
                commandline = ["tfcbm"]

                options = {
                    "reason": GLib.Variant("s", "TFCBM clipboard history manager"),
                    "autostart": GLib.Variant("b", enable),
                    "commandline": GLib.Variant("as", commandline),
                    "dbus-activatable": GLib.Variant("b", False),
                }

                request_variant = GLib.Variant("(sa{sv})", ("", options))

            except Exception as variant_error:
                logger.error(f"Error building Variant: {variant_error}")
                raise

            result = proxy.call_sync(
                "RequestBackground",
                request_variant,
                Gio.DBusCallFlags.NONE,
                -1,
                None
            )

            try:
                self.settings.update_settings(**{"application.autostart_enabled": enable})
            except Exception as settings_error:
                logger.error(f"Error updating settings: {settings_error}")
                raise

            if enable:
                self.on_notification("Autostart enabled successfully.")
            else:
                self.on_notification("Autostart disabled successfully.")
            return True

        except GLib.Error as e:
            logger.debug(f"Portal not available (will try fallback): {e}")
            return False
        except Exception as e:
            logger.debug(f"Portal call failed (will try fallback): {e}")
            return False

    def _on_autostart_toggled(self, switch, _param):
        """Handle autostart toggle using the appropriate method for the environment."""
        is_enabled = switch.get_active()

        if self._is_running_in_flatpak():
            # Flatpak: must use portal (desktop file write is sandboxed)
            success = self._set_autostart_via_portal(is_enabled)
            if not success:
                self.on_notification(
                    "Autostart requires xdg-desktop-portal-xapp 1.0.7+ (XFCE/MATE) or portal support."
                )
        else:
            # Native: try portal first, fall back to desktop file
            success = self._set_autostart_via_portal(is_enabled)
            if not success:
                success = self._set_autostart_via_desktop_file(is_enabled)

        if not success:
            # Block signal while reverting to prevent loop
            self.startup_switch.handler_block(self._autostart_handler_id)
            switch.set_active(not is_enabled)
            self.startup_switch.handler_unblock(self._autostart_handler_id)

    def _is_running_in_flatpak(self) -> bool:
        """Check if running inside a Flatpak sandbox."""
        return Path("/.flatpak-info").exists()

    def _get_installed_app_id(self):
        """Get the app ID."""
        return 'io.github.dyslechtchitect.tfcbm'

    def _set_autostart_via_desktop_file(self, enable: bool) -> bool:
        """Fallback: set autostart using traditional .desktop file in ~/.config/autostart/."""
        logger.info(f"Trying desktop file fallback for autostart: enable={enable}")

        autostart_dir = Path.home() / ".config" / "autostart"
        desktop_file = autostart_dir / "io.github.dyslechtchitect.tfcbm.desktop"

        try:
            if enable:
                # Create autostart directory if needed
                autostart_dir.mkdir(parents=True, exist_ok=True)

                # Write desktop entry
                desktop_content = """[Desktop Entry]
Type=Application
Name=TFCBM
Comment=The * Clipboard Manager
Exec=tfcbm
Icon=io.github.dyslechtchitect.tfcbm
Terminal=false
Categories=Utility;
StartupNotify=false
X-GNOME-Autostart-enabled=true
"""
                desktop_file.write_text(desktop_content)
                logger.info(f"Created autostart desktop file: {desktop_file}")
            else:
                # Remove desktop file if it exists
                if desktop_file.exists():
                    desktop_file.unlink()
                    logger.info(f"Removed autostart desktop file: {desktop_file}")

            # Update settings
            self.settings.update_settings(**{"application.autostart_enabled": enable})

            if enable:
                self.on_notification("Autostart enabled (desktop file).")
            else:
                self.on_notification("Autostart disabled.")
            return True

        except Exception as e:
            logger.error(f"Error setting autostart via desktop file: {e}")
            self.on_notification(f"Error: Failed to change autostart setting.")
            return False

    def _set_shortcut_listener_enabled(self, enabled: bool):
        """Disable/enable the XDG Portal global shortcut listener."""
        target_window = self.window or self.parent_window
        if not target_window:
            return
        app = target_window.get_application()
        listener = getattr(app, 'shortcut_listener', None) if app else None
        if listener:
            if enabled:
                listener.enable()
            else:
                listener.disable()

    def _set_main_app_recording_state(self, is_recording: bool):
        """Set the recording state directly on the window."""
        target_window = self.window or self.parent_window

        if target_window:
            target_window.is_recording_shortcut = is_recording
            logger.info(f"Recording state set directly on window: {is_recording}")
        else:
            logger.warning("No window reference available to set recording state")
