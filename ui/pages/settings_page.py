"""Settings page component."""

import os
from pathlib import Path
from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk


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

    def build(self) -> Adw.PreferencesPage:
        settings_page = Adw.PreferencesPage()

        display_group = Adw.PreferencesGroup()
        display_group.set_title("Display Settings")
        display_group.set_description(
            "Configure how clipboard items are displayed"
        )

        item_width_row = Adw.SpinRow()
        item_width_row.set_title("Item Width")
        item_width_row.set_subtitle(
            "Width of clipboard item cards in pixels (50-1000)"
        )
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
        page_length_row.set_subtitle(
            "Maximum number of items to load per page (1-100)"
        )
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
