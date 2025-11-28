"""Item action buttons component."""

from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk


class ItemActions:
    def __init__(
        self,
        item: dict,
        on_copy: Callable[[], None],
        on_view: Callable[[], None],
        on_save: Callable[[], None],
        on_tags: Callable[[], None],
        on_delete: Callable[[], None],
    ):
        self.item = item
        self.on_copy = on_copy
        self.on_view = on_view
        self.on_save = on_save
        self.on_tags = on_tags
        self.on_delete = on_delete

    def build(self) -> Gtk.Widget:
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        header_box.set_hexpand(False)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        header_box.append(spacer)

        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        button_box.set_halign(Gtk.Align.END)

        self._add_copy_button(button_box)
        self._add_view_button(button_box)
        self._add_save_button(button_box)
        self._add_tags_button(button_box)
        self._add_delete_button(button_box)

        header_box.append(button_box)
        return header_box

    def _add_copy_button(self, container: Gtk.Box) -> None:
        button = Gtk.Button()
        button.set_icon_name("edit-copy-symbolic")
        button.add_css_class("flat")
        button.set_tooltip_text("Copy to clipboard")

        gesture = Gtk.GestureClick.new()
        gesture.connect("released", lambda *_: self._trigger_copy())
        gesture.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        button.add_controller(gesture)

        container.append(button)

    def _add_view_button(self, container: Gtk.Box) -> None:
        button = Gtk.Button()
        button.set_icon_name("zoom-in-symbolic")
        button.add_css_class("flat")
        button.set_tooltip_text("View full item")

        gesture = Gtk.GestureClick.new()
        gesture.connect("released", lambda *_: self._trigger_view())
        gesture.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        button.add_controller(gesture)

        container.append(button)

    def _add_save_button(self, container: Gtk.Box) -> None:
        button = Gtk.Button()
        button.set_icon_name("document-save-symbolic")
        button.add_css_class("flat")
        button.set_tooltip_text("Save to file")

        gesture = Gtk.GestureClick.new()
        gesture.connect("released", lambda *_: self._trigger_save())
        gesture.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        button.add_controller(gesture)

        container.append(button)

    def _add_tags_button(self, container: Gtk.Box) -> None:
        button = Gtk.Button()
        button.set_icon_name("bookmark-new-symbolic")
        button.add_css_class("flat")
        button.set_tooltip_text("Manage tags")

        css_provider = Gtk.CssProvider()
        css_data = (
            "button { color: #2e3436 !important; "
            "-gtk-icon-palette: error #2e3436; }"
        )
        css_provider.load_from_data(css_data.encode())
        button.get_style_context().add_provider(
            css_provider, Gtk.STYLE_PROVIDER_PRIORITY_USER
        )

        gesture = Gtk.GestureClick.new()
        gesture.connect("released", lambda *_: self._trigger_tags())
        gesture.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        button.add_controller(gesture)

        container.append(button)

    def _add_delete_button(self, container: Gtk.Box) -> None:
        button = Gtk.Button()
        button.set_icon_name("user-trash-symbolic")
        button.add_css_class("flat")
        button.set_tooltip_text("Delete item")

        gesture = Gtk.GestureClick.new()
        gesture.connect("released", lambda *_: self._trigger_delete())
        gesture.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        button.add_controller(gesture)

        container.append(button)

    def _trigger_copy(self) -> None:
        self.on_copy()

    def _trigger_view(self) -> None:
        self.on_view()

    def _trigger_save(self) -> None:
        self.on_save()

    def _trigger_tags(self) -> None:
        self.on_tags()

    def _trigger_delete(self) -> None:
        self.on_delete()
