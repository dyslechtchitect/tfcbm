"""Keyboard shortcut domain models."""
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class KeyboardShortcut:
    """Value object representing a keyboard shortcut."""

    modifiers: List[str]
    key: str

    def to_gtk_string(self) -> str:
        """
        Convert to GTK-style shortcut string.

        Returns:
            String like "<Ctrl><Shift>k"
        """
        modifier_str = "".join(f"<{mod}>" for mod in self.modifiers)
        return f"{modifier_str}{self.key}"

    def to_gsettings_string(self) -> str:
        """
        Convert to GSettings-compatible string.

        Returns:
            String with proper casing for GSettings
        """
        gtk_string = self.to_gtk_string()
        # GSettings expects specific casing
        replacements = {
            "ctrl": "Control",
            "alt": "Alt",
            "shift": "Shift",
            "super": "Super"
        }
        result = gtk_string
        for old, new in replacements.items():
            result = result.replace(old, new)
        return result.lower().replace("control", "Control").replace("alt", "Alt").replace("shift", "Shift").replace("super", "Super")

    def to_display_string(self) -> str:
        """
        Convert to human-readable display string.

        Returns:
            String like "Ctrl+Shift+K"
        """
        if not self.modifiers:
            return self.key
        modifier_str = "+".join(self.modifiers)
        return f"{modifier_str}+{self.key}"

    @classmethod
    def from_gtk_string(cls, shortcut_string: str) -> "KeyboardShortcut":
        """
        Parse GTK-style shortcut string.

        Args:
            shortcut_string: String like "<Ctrl><Shift>k"

        Returns:
            KeyboardShortcut instance
        """
        modifiers = []
        remaining = shortcut_string

        # Extract modifiers
        modifier_names = ["Ctrl", "Control", "Shift", "Alt", "Super", "Meta"]
        for mod in modifier_names:
            pattern = f"<{mod}>"
            if pattern in remaining:
                # Normalize to standard names
                normalized = mod
                if mod == "Control":
                    normalized = "Ctrl"
                if normalized not in modifiers:
                    modifiers.append(normalized)
                remaining = remaining.replace(pattern, "")

        # Remaining is the key
        key = remaining
        return cls(modifiers=modifiers, key=key)

    @classmethod
    def from_gsettings_array(cls, gsettings_output: str) -> "KeyboardShortcut":
        """
        Parse GSettings array output.

        Args:
            gsettings_output: String like "['<Control><Shift>k']"

        Returns:
            KeyboardShortcut instance
        """
        # Remove array brackets and quotes
        cleaned = gsettings_output.strip().strip("[]'\"")
        if not cleaned:
            raise ValueError("Empty shortcut string")
        return cls.from_gtk_string(cleaned)


# Modifier key names that should be ignored when recording
MODIFIER_ONLY_KEYS = frozenset([
    "Control_L", "Control_R",
    "Shift_L", "Shift_R",
    "Alt_L", "Alt_R",
    "Super_L", "Super_R",
    "Meta_L", "Meta_R"
])
