#!/usr/bin/env python3

"""
A simple GTK4 application for Fedora Linux (GNOME) that runs as a single
instance, exposes a D-Bus method, and allows the user to change the
keyboard shortcut used to activate it.
"""

import sys
import subprocess
import gi
import os
from enum import Enum, auto

# Require GTK & GDK 4 for the application
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gtk, Gio, GLib, Gdk

# --- Constants ---
DBUS_NAME = 'com.example.PopupApp'
DBUS_PATH = '/com/example/PopupApp'
DBUS_INTERFACE_NAME = 'com.example.PopupApp'
DBUS_INTERFACE_XML = f"""
<node>
  <interface name='{DBUS_INTERFACE_NAME}'><method name='Activate'></method></interface>
</node>
"""
DEFAULT_SHORTCUT = "<Primary><Shift>R"

class UIState(Enum):
    IDLE = auto()
    RECORDING = auto()
    CAPTURED = auto()

class PopupApp(Gtk.Application):
    """A single-instance GTK4 app that manages its own keyboard shortcut."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.application_id = 'com.example.popupapp.Gtk4.managed'
        self.window = None
        self._dbus_registration_id = 0

        self.ui_state = UIState.IDLE
        self.captured_accelerator = None

        self.shortcut_label = None
        self.record_button = None
        self.restore_button = None
        self.cancel_button = None
        self.save_button = None
        self.action_box = None
        self.info_label = None

        # Current hotkey (managed by GNOME extension)
        self.current_hotkey = DEFAULT_SHORTCUT

    def _update_shortcut_binding(self, binding_str):
        """Update the global hotkey binding in GNOME extension settings"""
        self.current_hotkey = binding_str
        # Update GNOME extension setting
        try:
            subprocess.run([
                'gsettings', 'set',
                'org.gnome.shell.extensions.popup-app-hotkey',
                'popup-app-hotkey',
                f"['{binding_str}']"
            ], check=True)
        except Exception as e:
            print(f"Failed to update extension hotkey: {e}", file=sys.stderr)
        self.shortcut_label.set_text(f"Current Shortcut: {binding_str}")
    
    def on_dbus_call(self, connection, sender, object_path, interface_name, method_name, params, invocation):
        if method_name == 'Activate':
            self.activate()
            invocation.return_value(None)
        return True

    def do_startup(self):
        Gtk.Application.do_startup(self)

        try:
            node_info = Gio.DBusNodeInfo.new_for_xml(DBUS_INTERFACE_XML)
            bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            self._dbus_registration_id = bus.register_object(
                object_path=DBUS_PATH,
                interface_info=node_info.interfaces[0],
                method_call_closure=self.on_dbus_call,
                get_property_closure=None,
                set_property_closure=None
            )
            Gio.bus_own_name(
                bus_type=Gio.BusType.SESSION, name=DBUS_NAME, flags=Gio.BusNameOwnerFlags.NONE,
                bus_acquired_closure=lambda c, n: print(f"D-Bus name '{n}' acquired."),
                name_acquired_closure=None, name_lost_closure=lambda c, n: print(f"Lost D-Bus name '{n}'")
            )
        except Exception as e:
            print(f"FATAL: D-Bus setup failed: {e}", file=sys.stderr)
            self.quit()

    def do_activate(self):
        if self.window:
            self.window.present()
            return

        self.window = Gtk.ApplicationWindow(application=self, title="Popup App Settings")
        self.window.set_default_size(450, 200)
        
        main_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15, margin_top=20, margin_bottom=20, margin_start=20, margin_end=20)
        self.window.set_child(main_vbox)

        self.shortcut_label = Gtk.Label(halign=Gtk.Align.CENTER)
        self.info_label = Gtk.Label(halign=Gtk.Align.CENTER)
        main_vbox.append(self.shortcut_label)
        main_vbox.append(self.info_label)

        self.action_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10, halign=Gtk.Align.CENTER, margin_top=10)
        main_vbox.append(self.action_box)

        self.record_button = Gtk.Button(label="Set New Shortcut")
        self.restore_button = Gtk.Button(label="Restore Default")
        self.cancel_button = Gtk.Button(label="Cancel")
        self.save_button = Gtk.Button(label="Save")

        self.record_button.connect("clicked", self.on_record_clicked)
        self.restore_button.connect("clicked", self.on_restore_clicked)
        self.cancel_button.connect("clicked", self.on_cancel_clicked)
        self.save_button.connect("clicked", self.on_save_clicked)

        evk = Gtk.EventControllerKey.new()
        evk.connect("key-pressed", self.on_key_pressed)
        self.window.add_controller(evk)
        
        self._update_ui_for_state()
        
        # Display current hotkey
        self.shortcut_label.set_text(f"Current Shortcut: {self.current_hotkey}")
        
        self.window.present()

    def do_shutdown(self):
        if self._dbus_registration_id > 0:
            bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            bus.unregister_object(self._dbus_registration_id)
        Gtk.Application.do_shutdown(self)

    def _update_ui_for_state(self):
        child = self.action_box.get_first_child()
        while child:
            self.action_box.remove(child)
            child = self.action_box.get_first_child()

        if self.ui_state == UIState.IDLE:
            self.info_label.set_text("")
            self.action_box.append(self.record_button)
            self.action_box.append(self.restore_button)
        elif self.ui_state == UIState.RECORDING:
            self.info_label.set_markup("<i>Press the desired key combination now…</i>")
            self.action_box.append(self.cancel_button)
        elif self.ui_state == UIState.CAPTURED:
            # Escape the accelerator string to avoid markup parsing issues
            import html
            escaped_accel = html.escape(self.captured_accelerator)
            self.info_label.set_markup(f"New shortcut: <b>{escaped_accel}</b>")
            self.action_box.append(self.save_button)
            self.action_box.append(self.cancel_button)

    def on_record_clicked(self, button):
        self.ui_state = UIState.RECORDING
        self._update_ui_for_state()

    def on_cancel_clicked(self, button):
        self.ui_state = UIState.IDLE
        self._update_ui_for_state()
        binding = self._run_gsettings(['get', f"{CUSTOM_KEYBINDING_SCHEMA}:{self.shortcut_gsettings_path}", 'binding'])
        self.shortcut_label.set_text(f"Current Shortcut: {binding}")

    def on_save_clicked(self, button):
        self._update_shortcut_binding(self.captured_accelerator)
        self.ui_state = UIState.IDLE
        self._update_ui_for_state()

        # Show restart message
        self._show_restart_dialog()

    def on_restore_clicked(self, button):
        self._update_shortcut_binding(DEFAULT_SHORTCUT)
        self.ui_state = UIState.IDLE
        self._update_ui_for_state()

        # Show restart message
        self._show_restart_dialog()

    def _show_restart_dialog(self):
        """Show dialog informing user to log out/in or restart GNOME Shell"""
        dialog = Gtk.MessageDialog(
            transient_for=self.window,
            modal=True,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text="Shortcut Set"
        )
        dialog.set_property("secondary-text",
            "Please log out and log back in or restart GNOME Shell to enable the new shortcut.\n\n"
            "To restart GNOME Shell:\n"
            "• Press Alt+F2\n"
            "• Type 'r' and press Enter"
        )
        dialog.connect("response", lambda d, r: d.destroy())
        dialog.present()

    def on_key_pressed(self, controller, keyval, keycode, state):
        if self.ui_state != UIState.RECORDING:
            return Gdk.EVENT_PROPAGATE

        try:
            is_modifier = (keyval in (Gdk.KEY_Control_L, Gdk.KEY_Control_R, Gdk.KEY_Shift_L, Gdk.KEY_Shift_R, Gdk.KEY_Alt_L, Gdk.KEY_Alt_R, Gdk.KEY_Super_L, Gdk.KEY_Super_R))
            if is_modifier:
                return Gdk.EVENT_PROPAGATE

            # Use Gtk.accelerator_name - works with GTK4
            accelerator = Gtk.accelerator_name(keyval, state)

            if accelerator:
                self.captured_accelerator = accelerator
                self.ui_state = UIState.CAPTURED
            else:
                self.ui_state = UIState.IDLE
        except Exception as e:
            print(f"An error occurred during key recording: {e}", file=sys.stderr)
            self.ui_state = UIState.IDLE
        finally:
            self._update_ui_for_state()

        return Gdk.EVENT_STOP

if __name__ == "__main__":
    app = PopupApp()
    sys.exit(app.run(sys.argv))