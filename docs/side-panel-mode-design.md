# Side Panel Mode - Design Document

## Overview

Implementation plan for adding a side panel display mode to TFCBM. This mode will transform the window into a narrow, transparent, always-on-top panel attached to the screen edge, with smooth slide-in/out animations.

## Requirements

### Visual Characteristics
- **Fixed positioning**: Edge-attached (left or right side)
- **Smart sizing**: Narrow width, height from below system tray to screen bottom
- **Visual effects**: Transparency, always-on-top
- **Animations**: Slide-in from edge when shown, slide-out when hidden
- **Compact UI**: More condensed card layout for better space utilization

### User-Configurable Settings
- Window mode (Normal / Side Panel)
- Side position (Left / Right)
- Panel width (220-400px)
- Opacity level (70-100%)
- Animation toggle

## Architecture

### 1. Settings Extension
**File**: `server/src/settings.py`

Add new `WindowSettings` class:

```python
class WindowSettings(BaseModel):
    """Window display and behavior settings"""
    mode: str = Field(
        default="normal",
        description="Window display mode: normal or side_panel"
    )
    side_panel_position: str = Field(
        default="left",
        description="Side panel position: left or right"
    )
    side_panel_width: int = Field(
        default=320,
        ge=220,
        le=400,
        description="Side panel width in pixels (220-400)"
    )
    side_panel_opacity: float = Field(
        default=0.90,
        ge=0.70,
        le=1.0,
        description="Side panel opacity (0.70-1.0)"
    )
    enable_animations: bool = Field(
        default=True,
        description="Enable slide-in/out animations"
    )
    animation_duration: int = Field(
        default=250,
        ge=100,
        le=500,
        description="Animation duration in milliseconds (100-500)"
    )
```

Add to `Settings` class:
```python
class Settings(BaseModel):
    """Main settings model"""
    display: DisplaySettings = Field(default_factory=DisplaySettings)
    retention: RetentionSettings = Field(default_factory=RetentionSettings)
    clipboard: ClipboardSettings = Field(default_factory=ClipboardSettings)
    window: WindowSettings = Field(default_factory=WindowSettings)  # NEW
```

### 2. Window Position Manager Enhancement
**File**: `ui/managers/window_position_manager.py`

Add new methods:

```python
def position_right(self) -> None:
    """Position window to the right side of the screen."""
    display = Gdk.Display.get_default()
    if display:
        monitor = display.get_monitors().get_item(0)
        geometry = monitor.get_geometry()
        surface = self.window.get_surface()
        if surface:
            # Get window width
            width = self.window.get_width()
            # Position at right edge
            x = geometry.width - width
            surface.toplevel_move(x, 0)
            logger.debug(f"Window positioned at right edge ({x}, 0)")

def get_monitor_workarea(self) -> tuple[int, int, int, int]:
    """Get usable screen area (excluding panels/tray).

    Returns:
        Tuple of (x, y, width, height) for workarea
    """
    display = Gdk.Display.get_default()
    if display:
        monitor = display.get_monitors().get_item(0)
        # Use workarea instead of geometry to respect panels
        workarea = monitor.get_workarea()
        return (workarea.x, workarea.y, workarea.width, workarea.height)
    return (0, 0, 1920, 1080)  # Fallback

def calculate_side_panel_geometry(self, width: int, position: str) -> tuple[int, int, int, int]:
    """Calculate side panel window geometry.

    Args:
        width: Desired panel width
        position: "left" or "right"

    Returns:
        Tuple of (x, y, width, height)
    """
    x, y, screen_width, screen_height = self.get_monitor_workarea()

    # Position based on side
    panel_x = x if position == "left" else (x + screen_width - width)
    panel_y = y  # Start from top of workarea (below tray)
    panel_width = width
    panel_height = screen_height  # Full workarea height

    return (panel_x, panel_y, panel_width, panel_height)
```

### 3. Slide Animation System
**New File**: `ui/animations/slide_animator.py`

```python
"""Window slide-in/out animation system."""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib
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
        self.animation = None

    def slide_in(self, direction: str, on_complete=None):
        """Animate window sliding in from edge.

        Args:
            direction: "left" or "right"
            on_complete: Optional callback when animation completes
        """
        surface = self.window.get_surface()
        if not surface:
            logger.warning("Cannot animate - no surface available")
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
        surface = self.window.get_surface()
        if not surface:
            logger.warning("Cannot animate - no surface available")
            return

        # Get current position
        current_x, current_y = self._get_current_position()

        # Calculate end position (off-screen)
        width = self.window.get_width()
        end_x = -width if direction == "left" else current_x + width

        # Animate to end position
        self._animate_position(current_x, end_x, current_y, on_complete)

    def _animate_position(self, start_x: int, end_x: int, y: int, on_complete):
        """Perform the actual animation using frame updates."""
        surface = self.window.get_surface()
        start_time = GLib.get_monotonic_time()
        duration_us = self.duration_ms * 1000

        def update_frame():
            current_time = GLib.get_monotonic_time()
            elapsed = current_time - start_time

            if elapsed >= duration_us:
                # Animation complete
                surface.toplevel_move(end_x, y)
                if on_complete:
                    on_complete()
                return False  # Stop animation

            # Calculate progress (0.0 to 1.0)
            progress = elapsed / duration_us
            # Apply easing (ease-out cubic)
            eased_progress = 1 - pow(1 - progress, 3)

            # Interpolate position
            current_x = int(start_x + (end_x - start_x) * eased_progress)
            surface.toplevel_move(current_x, y)

            return True  # Continue animation

        # Start animation loop
        GLib.timeout_add(16, update_frame)  # ~60 FPS

    def _get_target_position(self, direction: str) -> tuple[int, int]:
        """Get target position for the window."""
        from ui.managers.window_position_manager import WindowPositionManager
        position_manager = WindowPositionManager(self.window)

        width = self.window.get_width()
        x, y, screen_width, screen_height = position_manager.get_monitor_workarea()

        target_x = x if direction == "left" else (x + screen_width - width)
        target_y = y

        return (target_x, target_y)

    def _get_current_position(self) -> tuple[int, int]:
        """Get current window position."""
        # GTK4 doesn't expose position directly, return calculated position
        # This would need platform-specific implementation for accurate tracking
        # For now, return target position
        direction = "left"  # Would read from settings
        return self._get_target_position(direction)
```

### 4. Window Behavior Implementation
**File**: `ui/windows/clipboard_window.py`

Modify `__init__()` method around line 94-112:

```python
# Load settings
self.settings = get_settings()

# Set window properties based on mode
if self.settings.window.mode == "side_panel":
    self._configure_side_panel_mode()
else:
    self._configure_normal_mode()
```

Add new methods:

```python
def _configure_normal_mode(self):
    """Configure window for normal mode."""
    display = Gdk.Display.get_default()
    if display:
        monitors = display.get_monitors()
        if monitors and monitors.get_n_items() > 0:
            primary_monitor = monitors.get_item(0)
            monitor_geometry = primary_monitor.get_geometry()
            width = monitor_geometry.width // 3
            self.set_default_size(width, 800)
        else:
            self.set_default_size(350, 800)
    else:
        self.set_default_size(350, 800)

    self.set_resizable(True)
    # Keep default decorations

def _configure_side_panel_mode(self):
    """Configure window for side panel mode."""
    from ui.animations.slide_animator import SlideAnimator

    # Remove window decorations
    self.set_decorated(False)

    # Calculate geometry
    self.position_manager = WindowPositionManager(self)
    x, y, width, height = self.position_manager.calculate_side_panel_geometry(
        self.settings.window.side_panel_width,
        self.settings.window.side_panel_position
    )

    # Set size
    self.set_default_size(width, height)
    self.set_resizable(False)  # Fixed size in side panel mode

    # Apply transparency
    self.set_opacity(self.settings.window.side_panel_opacity)

    # Add CSS class for styling
    self.add_css_class("side-panel-mode")

    # Set always-on-top (platform-dependent)
    # GTK4 doesn't have direct API, use compositor hints via surface
    def apply_always_on_top():
        surface = self.get_surface()
        if surface:
            # This is X11/Wayland specific - may need platform detection
            try:
                from gi.repository import GdkX11
                if isinstance(surface, GdkX11.X11Surface):
                    # X11: Set _NET_WM_STATE_ABOVE
                    pass  # Would need X11 atoms
            except:
                pass

    self.connect("realize", lambda w: apply_always_on_top())

    # Initialize animator if animations enabled
    if self.settings.window.enable_animations:
        self.slide_animator = SlideAnimator(
            self,
            self.settings.window.animation_duration
        )
        # Trigger slide-in when window is shown
        self.connect("show", self._on_side_panel_show)
        self.connect("hide", self._on_side_panel_hide)

def _on_side_panel_show(self, widget):
    """Animate slide-in when showing side panel."""
    if hasattr(self, 'slide_animator'):
        self.slide_animator.slide_in(self.settings.window.side_panel_position)

def _on_side_panel_hide(self, widget):
    """Animate slide-out when hiding side panel."""
    if hasattr(self, 'slide_animator'):
        def actually_hide():
            # Hide after animation completes
            Gtk.Widget.hide(self)

        self.slide_animator.slide_out(
            self.settings.window.side_panel_position,
            on_complete=actually_hide
        )
        return True  # Prevent immediate hide
```

### 5. Compact Card Layout
**File**: `ui/style.css`

Add side panel specific styles:

```css
/* Side Panel Mode Styles */
window.side-panel-mode {
    background-color: alpha(@window_bg_color, 0.9);
    border-right: 1px solid alpha(@borders, 0.3);
}

window.side-panel-mode.left {
    border-right: 1px solid alpha(@borders, 0.3);
    border-left: none;
}

window.side-panel-mode.right {
    border-left: 1px solid alpha(@borders, 0.3);
    border-right: none;
}

/* Compact clipboard item cards in side panel mode */
window.side-panel-mode .clipboard-item {
    padding: 6px 8px;
    margin: 3px 4px;
}

window.side-panel-mode .clipboard-item-content {
    font-size: 0.9em;
}

window.side-panel-mode .clipboard-item-metadata {
    font-size: 0.75em;
    margin-top: 2px;
}

window.side-panel-mode .clipboard-item-buttons {
    padding: 2px;
}

window.side-panel-mode .clipboard-item-buttons button {
    min-width: 24px;
    min-height: 24px;
    padding: 2px;
}

/* Compact header in side panel mode */
window.side-panel-mode headerbar {
    min-height: 36px;
}

window.side-panel-mode headerbar button {
    min-width: 28px;
    min-height: 28px;
}

/* Compact search bar */
window.side-panel-mode .search-entry {
    margin: 4px 6px;
}

/* Compact tag display */
window.side-panel-mode .tag-pill {
    padding: 2px 6px;
    font-size: 0.75em;
    margin: 2px;
}
```

### 6. Settings UI
**File**: `ui/pages/settings_page.py`

Add window settings section (would need to read existing file first to see structure):

```python
# Window Display Settings Group
window_group = Adw.PreferencesGroup()
window_group.set_title("Window Display")
window_group.set_description("Configure window appearance and behavior")

# Mode selector
mode_row = Adw.ComboRow()
mode_row.set_title("Window Mode")
mode_row.set_subtitle("Normal window or side panel")
mode_model = Gtk.StringList.new(["Normal", "Side Panel"])
mode_row.set_model(mode_model)
mode_row.set_selected(0 if settings.window.mode == "normal" else 1)
mode_row.connect("notify::selected", self._on_window_mode_changed)
window_group.add(mode_row)

# Side position (only visible in side panel mode)
position_row = Adw.ComboRow()
position_row.set_title("Panel Position")
position_model = Gtk.StringList.new(["Left", "Right"])
position_row.set_model(position_model)
position_row.set_selected(0 if settings.window.side_panel_position == "left" else 1)
position_row.connect("notify::selected", self._on_position_changed)
window_group.add(position_row)

# Width slider
width_row = Adw.ActionRow()
width_row.set_title("Panel Width")
width_adjustment = Gtk.Adjustment(
    value=settings.window.side_panel_width,
    lower=220,
    upper=400,
    step_increment=10
)
width_scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=width_adjustment)
width_scale.set_hexpand(True)
width_scale.set_draw_value(True)
width_scale.connect("value-changed", self._on_width_changed)
width_row.add_suffix(width_scale)
window_group.add(width_row)

# Opacity slider
opacity_row = Adw.ActionRow()
opacity_row.set_title("Panel Opacity")
opacity_adjustment = Gtk.Adjustment(
    value=settings.window.side_panel_opacity * 100,
    lower=70,
    upper=100,
    step_increment=5
)
opacity_scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=opacity_adjustment)
opacity_scale.set_hexpand(True)
opacity_scale.set_draw_value(True)
opacity_scale.set_value_pos(Gtk.PositionType.RIGHT)
opacity_scale.connect("value-changed", self._on_opacity_changed)
opacity_row.add_suffix(opacity_scale)
window_group.add(opacity_row)

# Animation toggle
animation_row = Adw.SwitchRow()
animation_row.set_title("Enable Animations")
animation_row.set_subtitle("Slide-in/out when showing/hiding")
animation_row.set_active(settings.window.enable_animations)
animation_row.connect("notify::active", self._on_animation_toggled)
window_group.add(animation_row)
```

## Implementation Order

1. **Settings Schema** (`server/src/settings.py`)
   - Add `WindowSettings` class with all configuration options
   - Add to main `Settings` class
   - Test with default values

2. **Position Manager** (`ui/managers/window_position_manager.py`)
   - Add `position_right()` method
   - Add `get_monitor_workarea()` method
   - Add `calculate_side_panel_geometry()` method
   - Test positioning logic

3. **Basic Window Configuration** (`ui/windows/clipboard_window.py`)
   - Add mode detection in `__init__()`
   - Implement `_configure_side_panel_mode()`
   - Apply size, position, transparency
   - Test basic side panel appearance

4. **Animation System** (`ui/animations/slide_animator.py`)
   - Create `SlideAnimator` class
   - Implement slide-in/out with easing
   - Hook into window show/hide events
   - Test animations

5. **Compact Styles** (`ui/style.css`)
   - Add `.side-panel-mode` styles
   - Compact card layouts
   - Test visual appearance

6. **Settings UI** (`ui/pages/settings_page.py`)
   - Add window settings group
   - Wire up all controls to settings
   - Test settings persistence

7. **Testing & Polish**
   - Test on different screen sizes
   - Test with multiple monitors
   - Handle edge cases (no workarea data, etc.)
   - Polish animations and transitions

## Technical Notes

### Always-On-Top Challenges
GTK4 doesn't expose `gtk_window_set_keep_above()` directly. Potential solutions:
- Use `set_type_hint(Gdk.WindowTypeHint.DOCK)` for dock-like behavior
- Platform-specific compositor hints (X11 atoms, Wayland protocols)
- Focus management to keep window raised
- May require additional research for Wayland compatibility

### Animation Performance
- Use `GLib.timeout_add()` with 16ms interval (~60 FPS)
- Apply easing functions (ease-out cubic recommended)
- Consider `Adw.SpringAnimation` for spring-like motion
- Monitor performance on lower-end systems

### Transparency
- CSS `opacity` property affects entire window including decorations
- `set_opacity()` method is simpler but all-or-nothing
- For more control, use CSS with `alpha()` on specific elements
- Test with different GTK themes

### Screen Edge Detection
- Use `Gdk.Monitor.get_workarea()` instead of `get_geometry()`
- Workarea respects panels/docks/tray
- Handle cases where workarea might be unavailable (fallback to geometry)
- Support for multiple monitors (future enhancement)

## Future Enhancements

- Auto-hide on focus loss
- Hotkey to toggle panel visibility
- Multiple monitor support with monitor selection
- Adjustable panel height (not just full height)
- Different animation styles (fade, scale, etc.)
- Remember last position when switching modes