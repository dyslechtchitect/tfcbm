"""TFCBM About Dialog - DE-agnostic version using Gtk.AboutDialog"""

import random
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk
from ui.windows.license_window import LicenseWindow


# Funny taglines for about dialog
FUNNY_TAGLINES = [
    "Because Ctrl+C deserves better",
    "Making copy-paste great again",
    "The clipboard manager you didn't know you needed",
    "Your clipboard, but actually organized",
    "Remembering what you forgot you copied",
    "Clipboard management without the chaos",
    "Finally, a clipboard that works for you",
    "Copy once, paste forever",
    "Your digital memory keeper",
    "The friendly neighborhood clipboard manager",
    "Turning clipboard chaos into clipboard zen",
    "Where your copies feel at home",
    "Making clipboard history accessible",
    "Copy-paste, but make it better",
    "Your clipboard's new best friend",
]


def show_about_dialog(parent_window):
    """Show the about dialog.

    Args:
        parent_window: Parent window to present the dialog on
    """
    about = Gtk.AboutDialog()
    about.set_transient_for(parent_window)
    about.set_modal(True)

    # Pick a random funny tagline
    random_tagline = random.choice(FUNNY_TAGLINES)

    about.set_program_name("TFCBM")
    about.set_logo_icon_name("io.github.dyslechtchitect.tfcbm")
    about.set_version("1.1.1")
    about.set_comments(f"{random_tagline}\n\nA clipboard manager that keeps your copy-paste history organized and accessible.")
    about.set_website("https://github.com/dyslechtchitect/tfcbm")
    about.set_website_label("GitHub")
    about.set_authors(["TFCBM Developers"])
    about.set_copyright("\u00a9 2025 TFCBM Developers")
    about.set_license_type(Gtk.License.GPL_3_0)

    about.present()
