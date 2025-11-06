import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk

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
import os
if os.environ.get('WAYLAND_DISPLAY'):
    print("Wayland")
elif os.environ.get('DISPLAY'):
    print("X11")
else:
    print("Unknown")
