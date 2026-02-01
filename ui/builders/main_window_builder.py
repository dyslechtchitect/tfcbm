"""Builds the main application window UI - DE-agnostic GTK4 version."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import gi
from gi.repository import Gdk, Gio, Gtk

gi.require_version("Gtk", "4.0")


if TYPE_CHECKING:
    from ui.windows.clipboard_window import ClipboardWindow


@dataclass
class MainWindowWidgets:
    """Dataclass to hold the widgets of the main window."""

    main_box: Gtk.Box
    header: Gtk.HeaderBar
    title_stack: Gtk.Stack
    search_container: Gtk.Box
    button_stack: Gtk.Stack
    search_entry: Gtk.SearchEntry
    tag_flowbox: Gtk.Box
    main_stack: Gtk.Stack
    notebook: Gtk.Notebook
    copied_scrolled: Gtk.ScrolledWindow
    copied_listbox: Gtk.ListBox
    copied_loader: Gtk.Widget
    copied_status_label: Gtk.Label
    pasted_scrolled: Gtk.ScrolledWindow
    pasted_listbox: Gtk.ListBox
    pasted_loader: Gtk.Widget
    pasted_status_label: Gtk.Label
    user_tags_group: Gtk.ListBox
    notification_box: Gtk.Box
    notification_label: Gtk.Label
    filter_bar: Gtk.Box
    filter_toggle_btn: Gtk.ToggleButton
    filter_sort_btn: Gtk.Button
    builder: "MainWindowBuilder" = field(repr=False)

    # Compatibility properties for code that references tab_view/tab_bar
    @property
    def tab_view(self):
        return self.notebook

    @property
    def tab_bar(self):
        return self.notebook


class MainWindowBuilder:
    def __init__(self, window: "ClipboardWindow"):
        self.window = window
        self.filter_bar = None
        self.filter_toggle_btn = None
        self.filter_sort_btn = None
        self.filter_box = None
        self.system_filter_chips = []
        self.notebook = None

    def build(self) -> MainWindowWidgets:
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        header = Gtk.HeaderBar()
        header.add_css_class("tfcbm-header")

        title_stack = Gtk.Stack()
        header.set_title_widget(title_stack)

        title_label = Gtk.Label(label="TFCBM")
        title_label.add_css_class("title")
        title_label.add_css_class("tfcbm-title")
        title_stack.add_named(title_label, "main")

        settings_title_label = Gtk.Label(label="Settings")
        settings_title_label.add_css_class("title")
        settings_title_label.add_css_class("tfcbm-title")
        title_stack.add_named(settings_title_label, "settings")

        button_stack = Gtk.Stack()
        header.pack_end(button_stack)

        main_buttons = Gtk.Box()
        info_button = Gtk.Button()
        info_button.set_icon_name("help-about-symbolic")
        info_button.add_css_class("flat")
        info_button.connect("clicked", self.window._show_splash_screen)
        main_buttons.append(info_button)

        settings_button = Gtk.Button()
        settings_button.set_icon_name("emblem-system-symbolic")
        settings_button.add_css_class("flat")
        settings_button.connect("clicked", self.window._show_settings_page)
        main_buttons.append(settings_button)
        button_stack.add_named(main_buttons, "main")

        settings_buttons = Gtk.Box()
        back_button = Gtk.Button()
        back_button.set_icon_name("go-previous-symbolic")
        back_button.add_css_class("flat")
        back_button.connect("clicked", self.window._show_tabs_page)
        settings_buttons.append(back_button)
        button_stack.add_named(settings_buttons, "settings")

        # Header is set as the window titlebar (CSD) in ClipboardWindow,
        # not packed into main_box, to avoid a double header on DEs like KDE.

        search_container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        search_container.set_margin_start(8)
        search_container.set_margin_end(8)
        search_container.set_margin_top(8)
        search_container.set_margin_bottom(4)

        search_entry = Gtk.SearchEntry()
        search_entry.set_hexpand(True)
        search_entry.set_placeholder_text("Search clipboard items...")
        search_entry.connect("search-changed", self.window._on_search_changed)
        search_entry.connect("activate", self.window._on_search_activate)
        search_container.append(search_entry)

        main_box.append(search_container)

        tag_frame = Gtk.Frame()
        tag_frame.set_margin_start(8)
        tag_frame.set_margin_end(8)
        tag_frame.set_margin_top(4)
        tag_frame.set_margin_bottom(0)
        tag_frame.add_css_class("view")

        tag_container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        tag_container.set_margin_top(2)
        tag_container.set_margin_bottom(2)
        tag_container.set_margin_start(8)
        tag_container.set_margin_end(8)

        tag_scrolled = Gtk.ScrolledWindow()
        tag_scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        tag_scrolled.set_max_content_height(40)
        tag_scrolled.set_min_content_height(32)
        tag_scrolled.set_propagate_natural_height(True)
        tag_scrolled.set_hexpand(True)
        tag_scrolled.set_kinetic_scrolling(True)

        # Add mouse wheel scroll support
        scroll_controller = Gtk.EventControllerScroll.new(
            Gtk.EventControllerScrollFlags.HORIZONTAL
        )
        scroll_controller.connect("scroll", self._on_tag_scroll)
        tag_scrolled.add_controller(scroll_controller)

        # Use horizontal Box instead of FlowBox to prevent wrapping
        tag_flowbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        tag_scrolled.set_child(tag_flowbox)

        tag_container.append(tag_scrolled)

        # Store reference for scroll handling
        self.tag_scrolled = tag_scrolled

        add_tag_btn = Gtk.Button()
        add_tag_btn.set_icon_name("list-add-symbolic")
        add_tag_btn.add_css_class("flat")
        add_tag_btn.set_tooltip_text("Create new tag")
        add_tag_btn.set_valign(Gtk.Align.CENTER)
        css_provider_add = Gtk.CssProvider()
        css_data_add = "button { min-width: 20px; min-height: 20px; padding: 2px; }"
        css_provider_add.load_from_data(css_data_add.encode())
        add_tag_btn.get_style_context().add_provider(css_provider_add, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        add_tag_btn.connect("clicked", lambda btn: self.window._on_create_tag(btn))
        tag_container.append(add_tag_btn)

        clear_btn = Gtk.Button()
        clear_btn.set_icon_name("window-close-symbolic")
        clear_btn.add_css_class("flat")
        clear_btn.set_tooltip_text("Clear filter")
        clear_btn.set_valign(Gtk.Align.CENTER)
        css_provider = Gtk.CssProvider()
        css_data = "button { min-width: 20px; min-height: 20px; padding: 2px; }"
        css_provider.load_from_data(css_data.encode())
        clear_btn.get_style_context().add_provider(css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        clear_btn.connect("clicked", lambda btn: self.window._clear_tag_filter())
        tag_container.append(clear_btn)
        tag_frame.set_child(tag_container)

        main_stack = Gtk.Stack()
        main_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        main_stack.set_vexpand(True)
        main_stack.set_visible(False)  # Start hidden; notebook is the default view

        # Use Gtk.Notebook instead of Adw.TabView/TabBar
        self.notebook = Gtk.Notebook()
        self.notebook.set_vexpand(True)

        # Create Copied tab
        copied_scrolled = Gtk.ScrolledWindow()
        copied_scrolled.set_vexpand(True)
        copied_scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        copied_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        copied_footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        copied_footer.set_margin_top(8)
        copied_footer.set_margin_bottom(4)
        copied_footer.set_margin_start(8)
        copied_footer.set_margin_end(8)

        copied_status_label = Gtk.Label()
        copied_status_label.add_css_class("dim-label")
        copied_status_label.add_css_class("caption")
        copied_status_label.set_hexpand(True)
        copied_status_label.set_halign(Gtk.Align.START)
        copied_footer.append(copied_status_label)

        copied_listbox = Gtk.ListBox()
        copied_listbox.add_css_class("boxed-list")
        copied_listbox.set_selection_mode(Gtk.SelectionMode.NONE)

        copied_box.append(copied_listbox)

        copied_loader = self._create_loader()
        copied_loader.set_visible(False)
        copied_box.append(copied_loader)

        copied_box.append(copied_footer)

        copied_scrolled.set_child(copied_box)

        copied_vadj = copied_scrolled.get_vadjustment()
        copied_vadj.connect("value-changed", lambda adj: self.window._on_scroll_changed(adj, "copied"))

        # Create tab label with icon for Copied
        copied_tab_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        copied_tab_icon = Gtk.Image.new_from_icon_name("edit-copy-symbolic")
        copied_tab_icon.set_pixel_size(16)
        copied_tab_box.append(copied_tab_icon)
        copied_tab_box.append(Gtk.Label(label="Copied"))

        self.notebook.append_page(copied_scrolled, copied_tab_box)

        # Create Pasted tab
        pasted_scrolled = Gtk.ScrolledWindow()
        pasted_scrolled.set_vexpand(True)
        pasted_scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        pasted_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        pasted_footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        pasted_footer.set_margin_top(8)
        pasted_footer.set_margin_bottom(4)
        pasted_footer.set_margin_start(8)
        pasted_footer.set_margin_end(8)

        pasted_status_label = Gtk.Label()
        pasted_status_label.add_css_class("dim-label")
        pasted_status_label.add_css_class("caption")
        pasted_status_label.set_hexpand(True)
        pasted_status_label.set_halign(Gtk.Align.START)
        pasted_footer.append(pasted_status_label)

        pasted_listbox = Gtk.ListBox()
        pasted_listbox.add_css_class("boxed-list")
        pasted_listbox.set_selection_mode(Gtk.SelectionMode.NONE)

        pasted_box.append(pasted_listbox)

        pasted_loader = self._create_loader()
        pasted_loader.set_visible(False)
        pasted_box.append(pasted_loader)

        pasted_box.append(pasted_footer)

        pasted_scrolled.set_child(pasted_box)

        pasted_vadj = pasted_scrolled.get_vadjustment()
        pasted_vadj.connect("value-changed", lambda adj: self.window._on_scroll_changed(adj, "pasted"))

        # Create tab label with icon for Pasted
        pasted_tab_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        pasted_tab_icon = Gtk.Image.new_from_icon_name("edit-paste-symbolic")
        pasted_tab_icon.set_pixel_size(16)
        pasted_tab_box.append(pasted_tab_icon)
        pasted_tab_box.append(Gtk.Label(label="Pasted"))

        self.notebook.append_page(pasted_scrolled, pasted_tab_box)

        # Connect tab switch signal
        self.notebook.connect("switch-page", self.window._on_tab_switched)

        settings_page = self._create_settings_page()
        main_stack.add_named(settings_page, "settings")

        # Create user_tags_group as a ListBox for dynamic tag row management
        user_tags_group = Gtk.ListBox()
        user_tags_group.set_selection_mode(Gtk.SelectionMode.NONE)
        user_tags_group.add_css_class("boxed-list")

        # Add notebook (replaces tab_bar position in layout)
        main_box.append(self.notebook)

        self._create_filter_bar()
        main_box.append(self.filter_bar)

        main_box.append(main_stack)

        main_box.append(tag_frame)

        return MainWindowWidgets(
            main_box=main_box,
            header=header,
            title_stack=title_stack,
            search_container=search_container,
            button_stack=button_stack,
            search_entry=search_entry,
            tag_flowbox=tag_flowbox,
            main_stack=main_stack,
            notebook=self.notebook,
            copied_scrolled=copied_scrolled,
            copied_listbox=copied_listbox,
            copied_loader=copied_loader,
            copied_status_label=copied_status_label,
            pasted_scrolled=pasted_scrolled,
            pasted_listbox=pasted_listbox,
            pasted_loader=pasted_loader,
            pasted_status_label=pasted_status_label,
            user_tags_group=user_tags_group,
            notification_box=None,
            notification_label=None,
            filter_bar=self.filter_bar,
            filter_toggle_btn=self.filter_toggle_btn,
            filter_sort_btn=self.filter_sort_btn,
            builder=self,
        )

    def _on_tag_scroll(self, controller, dx, dy):
        """Handle mouse wheel scrolling on tags bar."""
        if not hasattr(self, 'tag_scrolled'):
            return False

        hadj = self.tag_scrolled.get_hadjustment()
        if not hadj:
            return False

        scroll_amount = dy * 30
        new_value = hadj.get_value() + scroll_amount
        new_value = max(hadj.get_lower(), min(new_value, hadj.get_upper() - hadj.get_page_size()))
        hadj.set_value(new_value)

        return True

    def _create_loader(self) -> Gtk.Widget:
        loader_path = Path(__file__).parent.parent.parent / "resouces" / "loader.svg"
        if loader_path.exists():
            picture = Gtk.Picture.new_for_filename(str(loader_path))
            picture.set_size_request(120, 120)
            picture.set_halign(Gtk.Align.CENTER)
            picture.set_valign(Gtk.Align.CENTER)
            picture.set_can_shrink(False)
            return picture
        else:
            spinner = Gtk.Spinner()
            spinner.set_size_request(24, 24)
            spinner.set_halign(Gtk.Align.CENTER)
            spinner.set_valign(Gtk.Align.CENTER)
            spinner.start()
            return spinner

    def _create_filter_bar(self):
        self.filter_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.filter_bar.set_margin_top(6)
        self.filter_bar.set_margin_bottom(6)
        self.filter_bar.set_margin_start(8)
        self.filter_bar.set_margin_end(8)
        self.filter_bar.add_css_class("toolbar")
        self.filter_bar.set_visible(True)

        self.filter_toggle_btn = Gtk.ToggleButton()
        icon_found = False
        for icon_name in [
            "funnel-symbolic",
            "filter-symbolic",
            "view-filter-symbolic",
            "preferences-system-symbolic",
        ]:
            theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
            if theme.has_icon(icon_name):
                self.filter_toggle_btn.set_icon_name(icon_name)
                icon_found = True
                break
        if not icon_found:
            self.filter_toggle_btn.set_label("Filter")

        self.filter_toggle_btn.set_tooltip_text("Show/hide system filters")
        self.filter_toggle_btn.add_css_class("flat")
        self.filter_toggle_btn.set_size_request(32, 32)
        self.filter_toggle_btn.set_visible(True)
        self.filter_toggle_btn.set_sensitive(True)

        self.filter_scroll = Gtk.ScrolledWindow()
        self.filter_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        self.filter_scroll.set_hexpand(True)

        self.filter_box = Gtk.FlowBox()
        self.filter_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self.filter_box.set_homogeneous(False)
        self.filter_box.set_column_spacing(4)
        self.filter_box.set_row_spacing(4)
        self.filter_box.set_max_children_per_line(20)

        self.filter_scroll.set_child(self.filter_box)
        self.filter_bar.append(self.filter_scroll)

        clear_btn = Gtk.Button()
        clear_btn.set_icon_name("edit-clear-symbolic")
        clear_btn.set_tooltip_text("Clear all filters")
        clear_btn.add_css_class("flat")
        clear_btn.connect("clicked", self.window._on_clear_filters)
        self.filter_bar.append(clear_btn)

        separator = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        self.filter_bar.append(separator)

        self.filter_sort_btn = Gtk.Button()
        self.filter_sort_btn.set_icon_name("view-sort-descending-symbolic")
        self.filter_sort_btn.set_tooltip_text("Newest first")
        self.filter_sort_btn.add_css_class("flat")
        self.filter_sort_btn.add_css_class("sort-toggle")
        self.filter_sort_btn.connect("clicked", lambda btn: self.window._toggle_sort_from_toolbar())
        self.filter_bar.append(self.filter_sort_btn)

        jump_btn = Gtk.Button()
        jump_btn.set_icon_name("go-top-symbolic")
        jump_btn.set_tooltip_text("Jump to top")
        jump_btn.add_css_class("flat")
        jump_btn.connect("clicked", lambda btn: self.window._jump_to_top_from_toolbar())
        self.filter_bar.append(jump_btn)
        self._add_system_filters()

    def _add_system_filters(self):
        self.system_filter_chips = []
        system_filters = [
            ("text", "Text", "text-x-generic-symbolic"),
            ("image", "Images", "image-x-generic-symbolic"),
            ("url", "URLs", "web-browser-symbolic"),
            ("file", "Files", "folder-documents-symbolic"),
        ]

        for filter_type, label, icon_name in system_filters:
            chip = self._create_filter_chip(filter_type, label, icon_name, is_system=True)
            self.system_filter_chips.append(chip)

    def _create_filter_chip(self, filter_id, label, icon_name=None, is_system=False):
        chip = Gtk.ToggleButton()
        chip.set_has_frame(False)
        chip.add_css_class("pill")

        chip_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)

        if icon_name:
            icon = Gtk.Image.new_from_icon_name(icon_name)
            icon.set_pixel_size(12)
            chip_box.append(icon)

        chip_label = Gtk.Label(label=label)
        chip_label.add_css_class("caption")
        chip_box.append(chip_label)

        chip.set_child(chip_box)
        chip.connect("toggled", lambda btn: self.window._on_filter_toggled(filter_id, btn))

        flow_child = Gtk.FlowBoxChild()
        flow_child.set_child(chip)

        if is_system:
            flow_child.set_visible(True)

        self.filter_box.append(flow_child)

        return flow_child

    def _create_settings_page(self):
        # Use the proper SettingsPage class which includes keyboard shortcut recorder
        from ui.pages.settings_page import SettingsPage

        settings_page_obj = SettingsPage(
            settings=self.window.settings,
            on_notification=self.window.show_notification,
            window=self.window  # Pass window reference for direct communication
        )
        settings_page = settings_page_obj.build()

        return settings_page
