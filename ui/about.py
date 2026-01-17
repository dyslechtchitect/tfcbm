#!/usr/bin/env python3
"""
TFCBM About Dialog - Shows app information using Adw.AboutDialog
"""

import random
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw
from ui.windows.license_window import LicenseWindow


# Funny taglines for about dialog - clean and family-friendly
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
    about = Adw.AboutDialog()

    # Pick a random funny tagline for developer name subtitle
    random_tagline = random.choice(FUNNY_TAGLINES)

    about.set_application_name("TFCBM")
    about.set_application_icon("io.github.dyslechtchitect.tfcbm")
    about.set_version("1.0.0")
    about.set_developer_name(random_tagline)
    # about.set_license_type(Adw.License.GPL_3_0) # Removed as Adw.License is not available
    about.set_comments("A clipboard manager for GNOME that keeps your copy-paste history organized and accessible.")
    about.set_website("https://github.com/dyslechtchitect/tfcbm")
    about.set_issue_url("https://github.com/dyslechtchitect/tfcbm/issues")

    # Add link to README
    about.add_link("Documentation", "https://github.com/dyslechtchitect/tfcbm#readme")
    about.add_link("View License", "view-license")

    def on_activate_link(dialog, uri):
        if uri == "view-license":
            license_win = LicenseWindow(parent=parent_window)
            license_win.present()
            return True  # We handled this custom URI
        return False  # Let default handler open external URLs

    about.connect("activate-link", on_activate_link)


    # Add developers
    about.set_developers([
        "TFCBM Developers"
    ])

    # Add copyright
    about.set_copyright("© 2025 TFCBM Developers")

    # Present the dialog with parent window
    about.present(parent_window)
