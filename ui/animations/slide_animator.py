"""Window slide-in/out animation system."""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")

from gi.repository import Gdk, GLib
import logging

logger = logging.getLogger("TFCBM.SlideAnimator")


class SlideAnimator:
    """Manages slide-in/out animations for side panel mode."""

    def __init__(self, window, duration_ms: int = 250):
        """Initialize animator.

        Args:
            window: The window to animate
            duration_ms: Animation duration in milliseconds
        """
        self.window = window
        self.duration_ms = duration_ms
        self.animation_active = False

    def slide_in(self, direction: str, on_complete=None):
        """Animate window sliding in from edge.

        Args:
            direction: "left" or "right"
            on_complete: Optional callback when animation completes
        """
        if self.animation_active:
            logger.warning("Animation already in progress, skipping")
            return

        surface = self.window.get_surface()
        if not surface:
            logger.warning("Cannot animate - no surface available")
            if on_complete:
                on_complete()
            return

        # Get target position (final resting position)
        target_x, target_y = self._get_target_position(direction)

        # Calculate starting position (off-screen)
        width = self.window.get_width()
        start_x = -width if direction == "left" else target_x + width

        # Move to start position immediately
        surface.toplevel_move(start_x, target_y)

        # Animate to target position
        self._animate_position(start_x, target_x, target_y, on_complete)

    def slide_out(self, direction: str, on_complete=None):
        """Animate window sliding out to edge.

        Args:
            direction: "left" or "right"
            on_complete: Optional callback when animation completes
        """
        if self.animation_active:
            logger.warning("Animation already in progress, skipping")
            return

        surface = self.window.get_surface()
        if not surface:
            logger.warning("Cannot animate - no surface available")
            if on_complete:
                on_complete()
            return

        # Get current position (assume it's at the target position)
        current_x, current_y = self._get_target_position(direction)

        # Calculate end position (off-screen)
        width = self.window.get_width()
        end_x = -width if direction == "left" else current_x + width

        # Animate to end position
        self._animate_position(current_x, end_x, current_y, on_complete)

    def _animate_position(self, start_x: int, end_x: int, y: int, on_complete):
        """Perform the actual animation using frame updates."""
        surface = self.window.get_surface()
        if not surface:
            if on_complete:
                on_complete()
            return

        self.animation_active = True
        start_time = GLib.get_monotonic_time()
        duration_us = self.duration_ms * 1000

        def update_frame():
            if not self.animation_active:
                return False

            current_time = GLib.get_monotonic_time()
            elapsed = current_time - start_time

            if elapsed >= duration_us:
                # Animation complete
                surface.toplevel_move(end_x, y)
                self.animation_active = False
                if on_complete:
                    on_complete()
                return False  # Stop animation

            # Calculate progress (0.0 to 1.0)
            progress = elapsed / duration_us
            # Apply easing (ease-out cubic for smooth deceleration)
            eased_progress = 1 - pow(1 - progress, 3)

            # Interpolate position
            current_x = int(start_x + (end_x - start_x) * eased_progress)
            surface.toplevel_move(current_x, y)

            return True  # Continue animation

        # Start animation loop (~60 FPS)
        GLib.timeout_add(16, update_frame)

    def _get_target_position(self, direction: str) -> tuple[int, int]:
        """Get target position for the window.

        Args:
            direction: "left" or "right"

        Returns:
            Tuple of (x, y) coordinates
        """
        from ui.managers.window_position_manager import WindowPositionManager

        position_manager = WindowPositionManager(self.window)
        x, y, screen_width, screen_height = position_manager.get_monitor_workarea()

        width = self.window.get_width()
        target_x = x if direction == "left" else (x + screen_width - width)
        target_y = y

        return (target_x, target_y)
