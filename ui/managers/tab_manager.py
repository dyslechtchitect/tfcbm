"""Tab switching and state management."""

from typing import Any

import gi
from gi.repository import GLib

gi.require_version("Gtk", "4.0")


class TabManager:
    """Manages tab switching logic and tab-specific state."""

    def __init__(
        self,
        window_instance: Any,
        filter_bar: Any,
        search_manager: Any = None,
    ):
        """Initialize TabManager.

        Args:
            window_instance: Reference to the ClipboardWindow instance
            filter_bar: GTK widget for the filter bar
            search_manager: SearchManager instance for handling search state
        """
        self.window = window_instance
        self.filter_bar = filter_bar
        self.search_manager = search_manager
        self.current_tab = "copied"

    def handle_tab_switched(self, tab_view: Any, param: Any) -> None:
        """Handle tab switching events.

        Args:
            tab_view: The TabView widget
            param: Parameter from notify signal
        """
        selected_page = tab_view.get_selected_page()
        if not selected_page:
            return

        # Clear search if active when switching tabs
        if self.search_manager and self.search_manager.is_active():
            print(
                f"[DEBUG] Clearing search, query was: '{self.search_manager.get_query()}'"
            )
            self.search_manager.clear()
            if hasattr(self.window, 'search_entry'):
                self.window.search_entry.set_text("")
            if hasattr(self.window, '_restore_normal_view'):
                self.window._restore_normal_view()

        title = selected_page.get_title()
        print(f"[DEBUG] Tab switched to: {title}", flush=True)

        if title == "Recently Pasted":
            self._handle_pasted_tab()
        elif title == "Recently Copied":
            self._handle_copied_tab()
        else:
            self._handle_other_tab(title)

    def _handle_pasted_tab(self) -> None:
        """Handle switching to Recently Pasted tab."""
        self.current_tab = "pasted"
        # Reset pagination and reload pasted items from the beginning
        self.window.history_loader.reset_pagination("pasted")
        # Load pasted items when switching to pasted tab
        GLib.idle_add(self.window.history_loader.load_pasted_history)
        # Show filter bar on clipboard tabs
        self.filter_bar.set_visible(True)
        print(
            f"[DEBUG] Filter bar shown for Pasted tab, visible: {self.filter_bar.get_visible()}",
            flush=True,
        )

    def _handle_copied_tab(self) -> None:
        """Handle switching to Recently Copied tab."""
        self.current_tab = "copied"
        # Show filter bar on clipboard tabs
        self.filter_bar.set_visible(True)
        print(
            f"[DEBUG] Filter bar shown for Copied tab, visible: {self.filter_bar.get_visible()}",
            flush=True,
        )

    def _handle_other_tab(self, title: str) -> None:
        """Handle switching to Settings or Tags tab.

        Args:
            title: The title of the tab
        """
        self.current_tab = "copied"
        # Hide filter bar on other tabs (Settings, Tags)
        self.filter_bar.set_visible(False)
        print(
            f"[DEBUG] Filter bar hidden for {title} tab, visible: {self.filter_bar.get_visible()}",
            flush=True,
        )

    def get_current_tab(self) -> str:
        """Get the currently active tab.

        Returns:
            The current tab name ("copied" or "pasted")
        """
        return self.current_tab
