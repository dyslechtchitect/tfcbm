"""Color utility functions for CSS generation."""

import re
import logging

logger = logging.getLogger("TFCBM.ColorUtils")


def sanitize_color(color: str) -> str:
    """
    Sanitize a color value for use in CSS.

    Args:
        color: A color string (hex, rgb, rgba, or named color)

    Returns:
        A sanitized color string safe for CSS, or a default gray if invalid
    """
    original_color = color

    if not color:
        return "#9a9996"

    # Clean whitespace and common issues
    color = color.strip()

    # Remove any trailing semicolons or other junk
    color = color.rstrip(';').strip()

    # Validate hex color (#RGB or #RRGGBB or #RRGGBBAA)
    if color.startswith('#'):
        hex_match = re.match(r'^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$', color)
        if hex_match:
            return color
        else:
            # Invalid hex, log and return default
            logger.warning(f"Invalid hex color '{original_color}' (after strip: '{color}'), using default gray")
            return "#9a9996"

    # Validate rgb/rgba
    if color.startswith('rgb'):
        # Basic validation for rgb(a) format
        if re.match(r'^rgba?\s*\([^)]+\)$', color):
            return color
        else:
            logger.warning(f"Invalid rgb color '{original_color}' (after strip: '{color}'), using default gray")
            return "#9a9996"

    # For named colors or other formats, do basic validation
    # Only allow alphanumeric and safe characters
    if re.match(r'^[a-zA-Z0-9\s]+$', color):
        return color

    # If we get here, it's invalid
    logger.warning(f"Invalid color format '{original_color}' (after strip: '{color}'), using default gray")
    return "#9a9996"


def hex_to_rgba(hex_color: str, alpha: float = 1.0) -> str:
    """
    Convert hex color to rgba format.

    Args:
        hex_color: Hex color string (e.g., "#ff0000" or "#f00")
        alpha: Alpha value between 0 and 1

    Returns:
        RGBA color string (e.g., "rgba(255, 0, 0, 1.0)")
    """
    # Sanitize first
    hex_color = sanitize_color(hex_color)

    # Parse hex color
    color_hex = hex_color.lstrip("#")

    try:
        if len(color_hex) == 3:
            r = int(color_hex[0] * 2, 16)
            g = int(color_hex[1] * 2, 16)
            b = int(color_hex[2] * 2, 16)
        elif len(color_hex) >= 6:
            r = int(color_hex[0:2], 16)
            g = int(color_hex[2:4], 16)
            b = int(color_hex[4:6], 16)
        else:
            # Invalid format, return gray
            return "rgba(154, 153, 150, 1.0)"

        # Clamp alpha between 0 and 1
        alpha = max(0.0, min(1.0, alpha))

        return f"rgba({r}, {g}, {b}, {alpha})"
    except (ValueError, IndexError):
        # Parsing failed, return default gray
        return "rgba(154, 153, 150, 1.0)"
