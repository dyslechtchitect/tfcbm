"""Manages window positioning on screen."""

import logging
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")

from gi.repository import Gdk

logger = logging.getLogger("TFCBM.WindowPositionManager")


class WindowPositionManager:
    """Manages window positioning and screen placement."""

    def __init__(self, window: Any):
        """Initialize WindowPositionManager.

        Args:
            window: The window instance to manage positioning for
        """
        self.window = window

    def position_left(self) -> None:
        """Position window to the left side of the screen (coordinates 0, 0)."""
        display = Gdk.Display.get_default()
        if display:
            surface = self.window.get_surface()
            if surface:
                # Move to left edge (top-left corner)
                surface.toplevel_move(0, 0)
                logger.debug("Window positioned at left edge (0, 0)")

    def position_right(self) -> None:
        """Position window to the right side of the screen."""
        display = Gdk.Display.get_default()
        if display:
            monitors = display.get_monitors()
            if monitors and monitors.get_n_items() > 0:
                primary_monitor = monitors.get_item(0)
                monitor_geometry = primary_monitor.get_geometry()

                # Get window's current width
                width = self.window.get_width()
                if width <= 0:
                    # Fallback if window hasn't been realized yet
                    width = 350

                # Calculate x position to place window at right edge
                x = monitor_geometry.width - width

                surface = self.window.get_surface()
                if surface:
                    # Move to right edge (top-right)
                    surface.toplevel_move(x, 0)
                    logger.debug(f"Window positioned at right edge ({x}, 0)")
