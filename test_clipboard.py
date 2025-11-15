import os

import gi
from gi.repository import Gdk, Gtk

gi.require_version("Gtk", "3.0")

print("Testing clipboard access...")

# Try both clipboard types
clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
primary = Gtk.Clipboard.get(Gdk.SELECTION_PRIMARY)

print("\nCLIPBOARD (Ctrl+C):")
text = clipboard.wait_for_text()
print(f"  Text: {text}")

print("\nPRIMARY (mouse selection):")
text_primary = primary.wait_for_text()
print(f"  Text: {text_primary}")

print("\nDisplay server:", end=" ")

if os.environ.get("WAYLAND_DISPLAY"):
    print("Wayland")
elif os.environ.get("DISPLAY"):
    print("X11")
else:
    print("Unknown")
