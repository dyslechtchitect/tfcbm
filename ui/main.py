#!/usr/bin/env python3
"""
TFCBM UI - GTK4 clipboard manager interface
"""

from gi.repository import Adw, Gdk, GdkPixbuf, Gio, GLib, Gtk, Pango
import websockets
import argparse
import asyncio
import base64
import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from settings import get_settings

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

# Configure logging with module name
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("TFCBM.UI")


class ClipboardItemRow(Gtk.ListBoxRow):
    """A row displaying a single clipboard item (text or image)"""

    def __init__(self, item, window, show_pasted_time=False):
        super().__init__()
        self.item = item
        self.window = window
        self.show_pasted_time = show_pasted_time
        self._last_paste_time = 0  # Track last paste to prevent duplicates

        # Get item dimensions from settings
        item_width = self.window.settings.item_width
        item_height = self.window.settings.item_height

        # Make row activatable for keyboard navigation (Enter/Space)
        self.set_activatable(True)
        # Connect activate signal to copy the item
        self.connect("activate", lambda row: self._on_row_clicked(self))

        # Main box for the row - FIXED HEIGHT, fills width
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        main_box.set_hexpand(True)  # Fill available width
        main_box.set_vexpand(False)  # Fixed height only - CRITICAL
        main_box.set_size_request(-1, item_height)  # Force fixed height, natural width

        # Create size group to enforce exact height
        main_box.set_valign(Gtk.Align.FILL)

        # Prevent natural height from exceeding requested height
        main_box.set_overflow(Gtk.Overflow.HIDDEN)

        # Card frame for styling
        card_frame = Gtk.Frame()
        card_frame.set_vexpand(False)
        card_frame.set_hexpand(True)  # Fill available width
        card_frame.set_size_request(-1, item_height)  # Fixed height, natural width
        card_frame.add_css_class("clipboard-item-card")
        card_frame.set_child(main_box)
        self.card_frame = card_frame

        # Row should fill width but maintain fixed height
        self.set_size_request(-1, item_height)
        self.set_vexpand(False)
        self.set_hexpand(True)

        # Add click gesture for single click (copy) and double click (open full view)
        click_gesture = Gtk.GestureClick.new()
        click_gesture.connect("released", self._on_card_clicked)
        card_frame.add_controller(click_gesture)

        # Header box with timestamp and buttons
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        header_box.set_hexpand(False)  # Prevent horizontal expansion

        # Timestamp label (show pasted time if in pasted tab, otherwise copied time)
        if show_pasted_time and "pasted_timestamp" in item:
            timestamp = item.get("pasted_timestamp", "")
            time_label_text = f"Pasted: {self._format_timestamp(timestamp)}"
        else:
            timestamp = item.get("timestamp", "")
            time_label_text = self._format_timestamp(timestamp)

        if timestamp:
            time_label = Gtk.Label(label=time_label_text)
            time_label.add_css_class("dim-label")
            time_label.add_css_class("caption")
            time_label.set_halign(Gtk.Align.START)
            # Removed time_label.set_hexpand(True)
            header_box.append(time_label)

        # Button box
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        button_box.set_halign(Gtk.Align.END)  # Align buttons to the end (right)

        # Copy button
        copy_button = Gtk.Button()
        copy_button.set_icon_name("edit-copy-symbolic")
        copy_button.add_css_class("flat")
        copy_button.set_tooltip_text("Copy to clipboard")
        copy_gesture = Gtk.GestureClick.new()
        copy_gesture.connect("released", lambda g, n, x, y: self._on_row_clicked(self))
        copy_gesture.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        copy_button.add_controller(copy_gesture)
        button_box.append(copy_button)

        # View Full Item button
        view_button = Gtk.Button()
        view_button.set_icon_name("zoom-in-symbolic")
        view_button.add_css_class("flat")
        view_button.set_tooltip_text("View full item")
        view_gesture = Gtk.GestureClick.new()
        view_gesture.connect("released", lambda g, n, x, y: self._do_view_full_item())
        view_gesture.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        view_button.add_controller(view_gesture)
        button_box.append(view_button)

        # Save button (with event controller to stop propagation)
        save_button = Gtk.Button()
        save_button.set_icon_name("document-save-symbolic")
        save_button.add_css_class("flat")
        save_button.set_tooltip_text("Save to file")

        # Use click gesture to stop propagation
        save_gesture = Gtk.GestureClick.new()
        save_gesture.connect("released", lambda g, n, x, y: self._do_save())
        save_gesture.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        save_button.add_controller(save_gesture)
        button_box.append(save_button)

        # Manage Tags button (with event controller to stop propagation)
        tags_button = Gtk.Button()
        tags_button.set_icon_name("tag-symbolic")
        tags_button.add_css_class("flat")
        tags_button.add_css_class("tags-button")
        tags_button.set_tooltip_text("Manage tags")
        self.tags_button = tags_button

        # Use click gesture to stop propagation
        tags_gesture = Gtk.GestureClick.new()
        tags_gesture.connect("released", lambda g, n, x, y: self._show_tags_popover())
        tags_gesture.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        tags_button.add_controller(tags_gesture)
        button_box.append(tags_button)

        # Delete button (with event controller to stop propagation)
        delete_button = Gtk.Button()
        delete_button.set_icon_name("user-trash-symbolic")
        delete_button.add_css_class("flat")
        delete_button.set_tooltip_text("Delete item")

        # Use click gesture to stop propagation
        delete_gesture = Gtk.GestureClick.new()
        delete_gesture.connect("released", lambda g, n, x, y: self._on_delete_clicked(delete_button))
        delete_gesture.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        delete_button.add_controller(delete_gesture)
        button_box.append(delete_button)

        header_box.append(button_box)
        main_box.append(header_box)

        # Content box - CONSTRAINED to not expand beyond card
        # Calculate available content space
        max_content_height = item_height - 50  # Account for header

        # Create a clipping container that fills width but fixed height
        content_clamp = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        content_clamp.set_size_request(-1, max_content_height)  # Fill width, fixed height
        content_clamp.set_overflow(Gtk.Overflow.HIDDEN)  # Clip content that exceeds bounds
        content_clamp.set_hexpand(True)  # Fill available width
        content_clamp.set_vexpand(False)

        # Content based on type
        if item["type"] == "text":
            # Create overlay to position opening quote at top-left and closing quote at bottom-right
            overlay = Gtk.Overlay()

            # Main text content box with opening quote
            text_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            text_box.set_halign(Gtk.Align.START)
            text_box.set_valign(Gtk.Align.START)

            # Opening quote - bigger and bold at top-left
            open_quote = Gtk.Label(label="\u201c")  # Left double quotation mark
            open_quote.add_css_class("big-quote")
            open_quote.set_valign(Gtk.Align.START)
            text_box.append(open_quote)

            # Actual content with proper width constraint
            content_label = Gtk.Label(label=item['content'])
            content_label.set_wrap(True)
            content_label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
            content_label.set_ellipsize(Pango.EllipsizeMode.END)  # Show ... at end
            content_label.set_lines(5)  # Maximum 5 lines - ellipsis will show on last line
            content_label.set_halign(Gtk.Align.START)
            content_label.set_valign(Gtk.Align.START)
            content_label.add_css_class("clipboard-item-text")
            content_label.add_css_class("typewriter-text")
            content_label.set_selectable(False)  # Make text non-selectable
            content_label.set_xalign(0)  # Left align text
            content_label.set_yalign(0)  # Top align text
            # Fill available width with ellipsization
            content_label.set_hexpand(True)
            content_label.set_vexpand(False)
            content_label.set_max_width_chars(-1)  # Disable character-based width (use natural width)
            text_box.append(content_label)

            # Set text_box as base of overlay
            overlay.set_child(text_box)

            # Closing quote - bigger and bold at BOTTOM-RIGHT
            close_quote = Gtk.Label(label="\u201d")  # Right double quotation mark
            close_quote.add_css_class("big-quote")
            close_quote.set_halign(Gtk.Align.END)  # Right align
            close_quote.set_valign(Gtk.Align.END)  # Bottom align
            overlay.add_overlay(close_quote)

            content_clamp.append(overlay)

        elif item["type"].startswith("image/") or item["type"] == "screenshot":
            try:
                # Use thumbnail if available, otherwise use full image
                thumbnail_data = item.get("thumbnail")
                image_data_b64 = thumbnail_data if thumbnail_data else item["content"]

                print(f"[UI] Loading image item {item.get('id')}, type: {item['type']}")
                print(
                    f"[UI] Has thumbnail: {
                        bool(thumbnail_data)}, data length: {
                        len(image_data_b64) if image_data_b64 else 0}"
                )

                if not image_data_b64:
                    raise Exception("No image data available")

                # Decode base64 image
                image_data = base64.b64decode(image_data_b64)
                print(f"[UI] Decoded image size: {len(image_data)} bytes")

                loader = GdkPixbuf.PixbufLoader()
                loader.write(image_data)
                loader.close()
                pixbuf = loader.get_pixbuf()

                print(f"[UI] Pixbuf loaded: {pixbuf.get_width()}x{pixbuf.get_height()}")

                # Create image widget and let GTK handle scaling with COVER mode
                texture = Gdk.Texture.new_for_pixbuf(pixbuf)
                picture = Gtk.Picture.new_for_paintable(texture)
                picture.set_halign(Gtk.Align.CENTER)  # Center image horizontally
                picture.set_valign(Gtk.Align.CENTER)  # Center image vertically
                picture.add_css_class("clipboard-item-image")  # Apply image styling
                picture.set_content_fit(Gtk.ContentFit.COVER)  # COVER to fill space and crop
                picture.set_hexpand(True)  # Fill width
                picture.set_vexpand(True)  # Fill height
                picture.set_can_shrink(True)  # Allow shrinking

                content_clamp.append(picture)
                print(f"[UI] ✓ Image widget added (will fill available space with COVER mode)")

            except Exception as e:
                error_label = Gtk.Label(label=f"Failed to load image: {str(e)}")
                error_label.add_css_class("error")
                error_label.set_selectable(True)  # Make error copyable
                error_label.set_wrap(True)
                content_clamp.append(error_label)

        main_box.append(content_clamp)

        # Create overlay to position tags at bottom right
        overlay = Gtk.Overlay()
        overlay.set_child(card_frame)

        # Tags display box (bottom right, small, semi-transparent)
        tags_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        tags_box.set_halign(Gtk.Align.END)
        tags_box.set_valign(Gtk.Align.END)
        tags_box.set_margin_end(6)
        tags_box.set_margin_bottom(6)
        self.tags_display_box = tags_box
        overlay.add_overlay(tags_box)

        self.set_child(overlay)  # Set the overlay as the child of the row

        # Display tags from item data
        item_tags = self.item.get('tags', [])
        self._display_tags(item_tags)

    def _format_timestamp(self, timestamp_str):
        """Format ISO timestamp to readable format"""

        try:
            dt = datetime.fromisoformat(timestamp_str)
            return dt.strftime("%H:%M:%S")
        except BaseException:
            return timestamp_str

    def _load_item_tags(self):
        """Load and display tags for this item"""
        def run_load():
            try:
                async def fetch_tags():
                    uri = "ws://localhost:8765"
                    async with websockets.connect(uri) as websocket:
                        request = {
                            "action": "get_item_tags",
                            "item_id": self.item.get("id")
                        }
                        await websocket.send(json.dumps(request))
                        response = await websocket.recv()
                        data = json.loads(response)

                        if data.get("type") == "item_tags":
                            tags = data.get("tags", [])
                            # Update UI on main thread
                            GLib.idle_add(self._display_tags, tags)

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(fetch_tags())
            except Exception as e:
                print(f"[UI] Error loading item tags: {e}")

        threading.Thread(target=run_load, daemon=True).start()

    def _display_tags(self, tags):
        """Display tags in the tags box (small, semi-transparent)"""
        # Clear existing tags
        while True:
            child = self.tags_display_box.get_first_child()
            if not child:
                break
            self.tags_display_box.remove(child)

        # Only show user-defined tags (not system tags)
        user_tags = [tag for tag in tags if not tag.get("is_system", False)]

        # Display up to 3 tags
        for tag in user_tags[:3]:
            tag_name = tag.get("name", "")
            tag_color = tag.get("color", "#9a9996")

            # Create small tag label
            label = Gtk.Label(label=tag_name)

            # Apply very small, semi-transparent styling with thin border
            css_provider = Gtk.CssProvider()
            css_data = f"label {{ background-color: alpha({tag_color}, 0.15); color: alpha({tag_color}, 0.8); font-size: 7pt; font-weight: normal; padding: 1px 4px; border: 1px solid alpha({tag_color}, 0.3); border-radius: 2px; }}"
            css_provider.load_from_data(css_data.encode())
            label.get_style_context().add_provider(
                css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

            self.tags_display_box.append(label)

        return False

    def _on_card_clicked(self, gesture, n_press, x, y):
        """Handle card clicks - single click copies, double click opens full view"""
        if n_press == 1:
            # Single click - copy to clipboard
            self._on_row_clicked(self)
        elif n_press == 2:
            # Double click - open full view
            self._do_view_full_item()

    def _on_row_clicked(self, row):
        """Copy item to clipboard when row is clicked"""
        self._perform_copy_to_clipboard(self.item["type"], self.item["id"], self.item["content"])

    def _perform_copy_to_clipboard(self, item_type, item_id, content=None):
        """Performs the actual copy to clipboard, shows toast, and records paste."""
        clipboard = Gdk.Display.get_default().get_clipboard()
        if not clipboard:
            print("Error: Could not get default clipboard.")
            self.window.show_toast("Error: Could not access clipboard.")
            return

        print(f"[UI] _perform_copy_to_clipboard called for item_id: {item_id}, type: {item_type}")
        print(f"[UI] Clipboard object: {clipboard}")

        try:
            if item_type == "text":
                if content is not None:
                    print(f"[UI] Attempting to copy text: {content[:50]}...")
                    try:
                        clipboard.set(content)
                        print(f"[UI] Successfully set text to clipboard: {content[:50]}")
                        self.window.show_toast("Text copied to clipboard")
                        self._record_paste(item_id)
                    except Exception as clipboard_e:
                        print(f"Error: Failed to set text to clipboard for item {item_id}: {clipboard_e}")
                        traceback.print_exc()
                        self.window.show_toast(f"Error setting clipboard: {str(clipboard_e)}")
                else:
                    print(f"Error: Text content is None for copy operation for item {item_id}.")
                    self.window.show_toast("Error copying text: content is empty.")
            elif item_type.startswith("image/") or item_type == "screenshot":
                self.window.show_toast("Loading full image...")
                self._copy_full_image_to_clipboard(item_id, clipboard)
        except Exception as e:
            print(f"Error setting clipboard content for item {item_id}: {e}")
            traceback.print_exc()
            self.window.show_toast(f"Error copying: {str(e)}")

    def _copy_full_image_to_clipboard(self, item_id, clipboard):
        """Request and copy full image from server to clipboard"""

        def fetch_and_copy():
            try:

                async def get_full_image():
                    uri = "ws://localhost:8765"
                    max_size = 5 * 1024 * 1024  # 5MB
                    async with websockets.connect(uri, max_size=max_size) as websocket:
                        # Request full image
                        request = {"action": "get_full_image", "id": item_id}
                        await websocket.send(json.dumps(request))

                        # Wait for response
                        response = await websocket.recv()
                        data = json.loads(response)

                        if data.get("type") == "full_image" and data.get("id") == item_id:
                            image_b64 = data.get("content")
                            image_data = base64.b64decode(image_b64)

                            # Load image into pixbuf
                            loader = GdkPixbuf.PixbufLoader()
                            loader.write(image_data)
                            loader.close()
                            pixbuf = loader.get_pixbuf()

                            # Copy to clipboard on main thread
                            def copy_to_clipboard_on_main_thread():
                                try:
                                    if not clipboard:
                                        print("Error: Clipboard object is None in copy_to_clipboard_on_main_thread.")
                                        self.window.show_toast("Error: Could not access clipboard.")
                                        return False

                                    # Convert pixbuf to PNG bytes for clipboard
                                    # Save pixbuf to PNG in memory
                                    success, png_bytes = pixbuf.save_to_bufferv("png", [], [])
                                    if not success:
                                        raise Exception("Failed to convert image to PNG")

                                    # Create GBytes from PNG data
                                    gbytes = GLib.Bytes.new(png_bytes)

                                    # Create content provider for PNG image
                                    content = Gdk.ContentProvider.new_for_bytes("image/png", gbytes)
                                    clipboard.set_content(content)

                                    print(
                                        f"Copied full image to clipboard ({pixbuf.get_width()}x{pixbuf.get_height()})"
                                    )
                                    self.window.show_toast(
                                        f"📷 Full image copied ({pixbuf.get_width()}x{pixbuf.get_height()})"
                                    )

                                    # Record paste event
                                    self._record_paste(item_id)
                                except Exception as e:
                                    print(f"Error copying to clipboard in main thread: {e}")

                                    traceback.print_exc()
                                    self.window.show_toast(f"Error copying: {str(e)}")
                                return False

                            GLib.idle_add(copy_to_clipboard_on_main_thread)

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(get_full_image())

            except Exception as e:
                error_msg = str(e)
                print(f"Error fetching full image: {error_msg}")

                traceback.print_exc()
                GLib.idle_add(lambda: self.window.show_toast(f"Error: {error_msg}") or False)

        # Run in background thread

        thread = threading.Thread(target=fetch_and_copy, daemon=True)
        thread.start()

    def _on_save_clicked(self, button):
        """Save item to file - stop event propagation"""
        # Stop the click from activating the row
        return True

    def _do_save(self):
        """Actually perform the save"""
        item_type = self.item["type"]
        item_id = self.item["id"]

        # Create file chooser dialog
        dialog = Gtk.FileDialog()

        if item_type == "text":
            dialog.set_initial_name("clipboard.txt")
        elif item_type.startswith("image/"):
            ext = item_type.split("/")[-1]
            dialog.set_initial_name(f"clipboard.{ext}")
        elif item_type == "screenshot":
            dialog.set_initial_name("screenshot.png")

        # Get the window
        window = self.get_root()

        def on_save_finish(dialog, result):
            try:
                file = dialog.save_finish(result)
                if file:
                    path = file.get_path()

                    if item_type == "text":
                        content = self.item["content"]
                        with open(path, "w") as f:
                            f.write(content)
                        print(f"Saved text to {path}")
                        self.window.show_toast(f"Saved text to {path}")
                    elif item_type.startswith("image/") or item_type == "screenshot":
                        # For images, request full image from server
                        self._save_full_image(item_id, path)

            except Exception as e:
                print(f"Error saving file: {e}")
                self.window.show_toast(f"Error saving file: {str(e)}")

        dialog.save(window, None, on_save_finish)

    def _do_view_full_item(self):
        """Display the full content of the item in a new dialog."""
        item_type = self.item["type"]
        item_id = self.item["id"]
        window = self.get_root()

        dialog = Adw.Window(modal=True, transient_for=window)
        dialog.set_title("Full Clipboard Item")
        dialog.set_default_size(600, 400)
        dialog.add_css_class("full-item-dialog")

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        main_box.set_margin_start(18)
        main_box.set_margin_end(18)
        main_box.set_margin_top(12)
        main_box.set_margin_bottom(12)

        # Header with timestamp
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        timestamp = self.item.get("timestamp", "")
        time_label = Gtk.Label(label=self._format_timestamp(timestamp))
        time_label.add_css_class("dim-label")
        time_label.add_css_class("caption")
        time_label.set_halign(Gtk.Align.START)
        time_label.set_hexpand(True)
        header_box.append(time_label)

        # Button box for save, delete, and close
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)

        save_button = Gtk.Button()
        save_button.set_icon_name("document-save-symbolic")
        save_button.set_tooltip_text("Save to file")
        save_button.connect("clicked", lambda btn: self._do_save())
        button_box.append(save_button)

        delete_button = Gtk.Button()
        delete_button.set_icon_name("user-trash-symbolic")
        delete_button.set_tooltip_text("Delete item")
        delete_button.connect("clicked", lambda btn: self._on_delete_clicked(btn, dialog))
        button_box.append(delete_button)

        # Close button
        close_button = Gtk.Button()
        close_button.set_icon_name("window-close-symbolic")
        close_button.set_tooltip_text("Close")
        close_button.connect("clicked", lambda btn: dialog.close())
        button_box.append(close_button)

        header_box.append(button_box)
        main_box.append(header_box)

        # Content area
        content_scrolled_window = Gtk.ScrolledWindow()
        content_scrolled_window.set_vexpand(True)
        content_scrolled_window.set_hexpand(True)

        if item_type == "text":
            content_label = Gtk.Label(label=self.item["content"])
            content_label.set_wrap(True)
            content_label.set_selectable(True)
            content_label.set_halign(Gtk.Align.START)
            content_label.set_valign(Gtk.Align.START)
            content_label.add_css_class("full-item-text")
            content_scrolled_window.set_child(content_label)

            # Make text clickable to copy
            text_copy_gesture = Gtk.GestureClick.new()
            text_copy_gesture.connect("released", lambda g, n, x, y: self._perform_copy_to_clipboard(item_type, item_id, self.item["content"]))
            content_label.add_controller(text_copy_gesture)
            content_label.set_cursor(Gdk.Cursor.new_from_name("pointer"))

        elif item_type.startswith("image/") or item_type == "screenshot":
            image_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            image_container.set_halign(Gtk.Align.CENTER)
            image_container.set_valign(Gtk.Align.CENTER)

            spinner = Gtk.Spinner()
            spinner.set_size_request(48, 48)
            spinner.start()
            image_container.append(spinner)

            # Placeholder for image
            picture = Gtk.Picture()
            picture.set_halign(Gtk.Align.CENTER)
            picture.set_valign(Gtk.Align.CENTER)
            picture.add_css_class("full-item-image")
            picture.set_can_shrink(False)
            picture.set_content_fit(Gtk.ContentFit.CONTAIN)
            image_container.append(picture)

            content_scrolled_window.set_child(image_container)

            # Make image clickable to copy
            image_copy_gesture = Gtk.GestureClick.new()
            image_copy_gesture.connect("released", lambda g, n, x, y: self._perform_copy_to_clipboard(item_type, item_id))
            picture.add_controller(image_copy_gesture)
            picture.set_cursor(Gdk.Cursor.new_from_name("pointer"))

            # Fetch full image in background
            def fetch_and_display_full_image():
                try:

                    async def get_full_image_data():
                        uri = "ws://localhost:8765"
                        async with websockets.connect(uri) as websocket:
                            request = {"action": "get_full_image", "id": item_id}
                            await websocket.send(json.dumps(request))
                            response = await websocket.recv()
                            data = json.loads(response)

                            if data.get("type") == "full_image" and data.get("id") == item_id:
                                image_b64 = data.get("content")
                                image_data = base64.b64decode(image_b64)

                                def update_image_on_ui():
                                    loader = GdkPixbuf.PixbufLoader()
                                    loader.write(image_data)
                                    loader.close()
                                    pixbuf = loader.get_pixbuf()
                                    texture = Gdk.Texture.new_for_pixbuf(pixbuf)
                                    picture.set_paintable(texture)
                                    spinner.stop()
                                    spinner.set_visible(False)
                                    print(f"Displayed full image {pixbuf.get_width()}x{pixbuf.get_height()}")
                                    return False

                                GLib.idle_add(update_image_on_ui)
                            else:
                                GLib.idle_add(lambda: self.window.show_toast("Failed to get full image data") or False)

                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(get_full_image_data())
                except Exception as e:
                    print(f"Error fetching full image for dialog: {e}")
                    GLib.idle_add(lambda: self.window.show_toast(f"Error loading image: {str(e)}") or False)
                    GLib.idle_add(spinner.stop)
                    GLib.idle_add(lambda: spinner.set_visible(False))

            threading.Thread(target=fetch_and_display_full_image, daemon=True).start()

        main_box.append(content_scrolled_window)

        dialog.set_content(main_box)
        dialog.present()

    def _save_full_image(self, item_id, path):
        """Request and save full image from server"""

        def fetch_and_save():
            try:

                async def get_full_image():
                    uri = "ws://localhost:8765"
                    max_size = 5 * 1024 * 1024  # 5MB
                    async with websockets.connect(uri, max_size=max_size) as websocket:
                        # Request full image
                        request = {"action": "get_full_image", "id": item_id}
                        await websocket.send(json.dumps(request))

                        # Wait for response
                        response = await websocket.recv()
                        data = json.loads(response)

                        if data.get("type") == "full_image" and data.get("id") == item_id:
                            image_b64 = data.get("content")
                            image_data = base64.b64decode(image_b64)

                            # Save to file
                            with open(path, "wb") as f:
                                f.write(image_data)

                            print(f"Saved full image to {path}")

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(get_full_image())

            except Exception as e:
                print(f"Error fetching full image: {e}")

        # Run in background thread

        thread = threading.Thread(target=fetch_and_save, daemon=True)
        thread.start()

    def _on_delete_clicked(self, button, full_item_dialog=None):
        """Delete item with confirmation"""
        window = self.get_root()

        # Create confirmation dialog
        dialog = Adw.AlertDialog.new(
            "Delete this item?", "This item will be permanently removed from your clipboard history."
        )

        dialog.add_response("cancel", "Nah")
        dialog.add_response("delete", "Yeah")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        def on_response(dialog, response):
            if response == "delete":
                # Send delete request via WebSocket
                self._delete_item_from_server(self.item["id"], full_item_dialog)

        dialog.connect("response", on_response)
        dialog.present(window)

    def _delete_item_from_server(self, item_id, full_item_dialog=None):
        """Send delete request to server via WebSocket"""

        def send_delete():
            try:

                async def delete_item():
                    uri = "ws://localhost:8765"
                    max_size = 5 * 1024 * 1024  # 5MB
                    async with websockets.connect(uri, max_size=max_size) as websocket:
                        # Send delete request
                        request = {"action": "delete_item", "id": item_id}
                        await websocket.send(json.dumps(request))
                        print(f"Deleted item {item_id}")
                        GLib.idle_add(lambda: self.window.show_toast(f"Item {item_id} deleted") or False)
                        if full_item_dialog:
                            GLib.idle_add(full_item_dialog.close)

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(delete_item())

            except Exception as e:
                print(f"Error deleting item: {e}")
                GLib.idle_add(lambda: self.window.show_toast(f"Error deleting item: {str(e)}") or False)

        # Run in background thread

        thread = threading.Thread(target=send_delete, daemon=True)
        thread.start()

    def _record_paste(self, item_id):
        """Record that this item was pasted (with debouncing to prevent duplicates)"""
        print(f"[UI] _record_paste called for item_id: {item_id}")

        # Debounce: Only record if at least 500ms has passed since last paste
        current_time = time.time()
        if current_time - self._last_paste_time < 0.5:
            print(f"[UI] Debouncing duplicate paste for item {item_id}")
            return
        self._last_paste_time = current_time

        def send_record():
            try:

                async def record():
                    uri = "ws://localhost:8765"
                    max_size = 5 * 1024 * 1024  # 5MB
                    async with websockets.connect(uri, max_size=max_size) as websocket:
                        request = {"action": "record_paste", "id": item_id}
                        print(f"[UI] Sending record_paste request for item {item_id}")
                        await websocket.send(json.dumps(request))
                        print(f"[UI] Recorded paste for item {item_id}")

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(record())

            except Exception as e:
                print(f"[UI] Error recording paste for item {item_id}: {e}")

        # Run in background thread

        thread = threading.Thread(target=send_record, daemon=True)
        thread.start()

    def _show_tags_popover(self):
        """Show popover to manage tags for this item"""
        # Create popover
        popover = Gtk.Popover()
        popover.set_parent(self.tags_button)
        popover.set_autohide(True)

        # Content box
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content_box.set_margin_top(12)
        content_box.set_margin_bottom(12)
        content_box.set_margin_start(12)
        content_box.set_margin_end(12)

        # Title
        title = Gtk.Label()
        title.set_markup("<b>Manage Tags</b>")
        title.set_halign(Gtk.Align.START)
        content_box.append(title)

        # Scrollable tag list
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_max_content_height(300)
        scroll.set_propagate_natural_height(True)

        # Tag list box
        tag_list = Gtk.ListBox()
        tag_list.set_selection_mode(Gtk.SelectionMode.NONE)
        tag_list.add_css_class("boxed-list")

        # Get item's current tags (we'll need to fetch these)
        item_id = self.item.get("id")

        # Get current tags for this item
        item_tags = self.item.get('tags', [])
        item_tag_ids = [tag.get('id') for tag in item_tags if isinstance(tag, dict)]
        print(f"[UI] Item {item_id} has tags: {item_tag_ids}")

        # Add all tags as checkbuttons
        for tag in self.window.all_tags:
            # Skip system tags - they can't be manually added
            if tag.get("is_system"):
                continue

            tag_id = tag.get("id")
            tag_name = tag.get("name", "")
            tag_color = tag.get("color", "#9a9996")

            # Create row with checkbutton
            row = Gtk.ListBoxRow()
            row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            row_box.set_margin_top(6)
            row_box.set_margin_bottom(6)
            row_box.set_margin_start(6)
            row_box.set_margin_end(6)

            # Color indicator
            color_box = Gtk.Box()
            color_box.set_size_request(16, 16)
            css_provider = Gtk.CssProvider()
            css_data = f"box {{ background-color: {tag_color}; border-radius: 3px; }}"
            css_provider.load_from_data(css_data.encode())
            color_box.get_style_context().add_provider(
                css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
            row_box.append(color_box)

            # Checkbutton with tag name
            check = Gtk.CheckButton()
            check.set_label(tag_name)
            check.set_hexpand(True)
            # Set initial state based on whether this item has this tag
            check.set_active(tag_id in item_tag_ids)
            handler_id = check.connect("toggled", lambda cb, tid=tag_id, iid=item_id: self._on_tag_toggle(cb, tid, iid, popover))
            # Store handler ID on the checkbutton for later blocking/unblocking
            check.handler_id = handler_id
            row_box.append(check)

            row.set_child(row_box)
            tag_list.append(row)

        scroll.set_child(tag_list)
        content_box.append(scroll)

        # No tags message
        if not any(not tag.get("is_system") for tag in self.window.all_tags):
            no_tags_label = Gtk.Label()
            no_tags_label.set_markup("<i>No custom tags available.\nCreate tags in the Tags tab.</i>")
            no_tags_label.set_justify(Gtk.Justification.CENTER)
            content_box.append(no_tags_label)

        popover.set_child(content_box)
        popover.popup()

    def _on_tag_toggle(self, checkbutton, tag_id, item_id, popover):
        """Handle tag checkbox toggle"""
        is_active = checkbutton.get_active()
        print(f"[UI] Tag toggle called: tag_id={tag_id}, item_id={item_id}, is_active={is_active}")

        def run_toggle():
            try:
                async def toggle_tag():
                    print(f"[UI] Connecting to WebSocket for tag toggle...")
                    uri = "ws://localhost:8765"
                    async with websockets.connect(uri) as websocket:
                        print(f"[UI] WebSocket connected")
                        if is_active:
                            request = {
                                "action": "add_item_tag",
                                "item_id": item_id,
                                "tag_id": tag_id
                            }
                        else:
                            request = {
                                "action": "remove_item_tag",
                                "item_id": item_id,
                                "tag_id": tag_id
                            }

                        print(f"[UI] Sending request: {request}")
                        await websocket.send(json.dumps(request))
                        response = await websocket.recv()
                        data = json.loads(response)
                        print(f"[UI] Received response: {data}")

                        # Check for success - server returns "success" type
                        if data.get("success") or data.get("type") in ["item_tag_added", "item_tag_removed", "success"]:
                            action = "added" if is_active else "removed"
                            GLib.idle_add(self.window.show_toast, f"Tag {action}")
                            print(f"[UI] Tag {action} successfully")
                            # Update item tags and refresh display
                            def update_tag_display():
                                # Find the tag in window.all_tags
                                tag_info = next((t for t in self.window.all_tags if t.get('id') == tag_id), None)
                                if tag_info:
                                    if is_active:
                                        # Add tag to item if not already there
                                        if 'tags' not in self.item:
                                            self.item['tags'] = []
                                        if tag_info not in self.item['tags']:
                                            self.item['tags'].append(tag_info)
                                    else:
                                        # Remove tag from item
                                        if 'tags' in self.item:
                                            self.item['tags'] = [t for t in self.item['tags'] if t.get('id') != tag_id]
                                    # Refresh tag display
                                    self._display_tags(self.item.get('tags', []))
                            GLib.idle_add(update_tag_display)
                        else:
                            print(f"[UI] Tag update failed - response: {data}")
                            GLib.idle_add(self.window.show_toast, "Failed to update tag")
                            # Revert checkbox on failure - use handler ID to block signal
                            def revert_checkbox():
                                if hasattr(checkbutton, 'handler_id'):
                                    checkbutton.handler_block(checkbutton.handler_id)
                                checkbutton.set_active(not is_active)
                                if hasattr(checkbutton, 'handler_id'):
                                    checkbutton.handler_unblock(checkbutton.handler_id)
                            GLib.idle_add(revert_checkbox)

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(toggle_tag())
            except Exception as e:
                print(f"[UI] Exception toggling tag: {e}")
                import traceback
                traceback.print_exc()
                GLib.idle_add(self.window.show_toast, f"Error: {e}")
                # Revert checkbox on error - use handler ID to block signal
                def revert_checkbox():
                    if hasattr(checkbutton, 'handler_id'):
                        checkbutton.handler_block(checkbutton.handler_id)
                    checkbutton.set_active(not is_active)
                    if hasattr(checkbutton, 'handler_id'):
                        checkbutton.handler_unblock(checkbutton.handler_id)
                GLib.idle_add(revert_checkbox)

        threading.Thread(target=run_toggle, daemon=True).start()


class ClipboardWindow(Adw.ApplicationWindow):
    """Main application window"""

    def __init__(self, app, server_pid=None):
        start_time = time.time()
        logger.info("Initializing ClipboardWindow...")
        super().__init__(application=app, title="TFCBM")
        self.server_pid = server_pid

        # Load settings
        self.settings = get_settings()

        # Connect close request handler
        self.connect("close-request", self._on_close_request)

        # Set window properties
        self.set_default_size(350, 800)
        self.set_resizable(True)

        # Pagination state
        self.copied_offset = 0
        self.copied_total = 0
        self.copied_has_more = True
        self.copied_loading = False

        self.pasted_offset = 0
        self.pasted_total = 0
        self.pasted_has_more = True
        self.pasted_loading = False

        self.page_size = self.settings.max_page_length

        # Window icon is set through the desktop file and application
        # GTK4/Adwaita doesn't use set_icon() anymore

        # Create toast overlay
        self.toast_overlay = Adw.ToastOverlay()

        # Create main box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Header bar with settings and close buttons
        header = Adw.HeaderBar()

        # Add small logo to header (left side)
        try:
            icon_path = Path(__file__).parent.parent / "resouces" / "tfcbm.svg"
            if icon_path.exists():
                # Create image from PNG
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(icon_path), 24, 24, True)
                texture = Gdk.Texture.new_for_pixbuf(pixbuf)
                logo_image = Gtk.Image.new_from_paintable(texture)
                logo_image.set_margin_start(4)
                logo_image.set_margin_end(4)
                logo_image.set_tooltip_text("TFCBM - The F*cking Clipboard Manager")
                header.pack_start(logo_image)
        except Exception as e:
            print(f"Warning: Could not load header logo: {e}")

        # Settings button (placeholder for now)
        settings_button = Gtk.Button()
        settings_button.set_icon_name("emblem-system-symbolic")
        settings_button.add_css_class("flat")
        header.pack_end(settings_button)

        main_box.append(header)

        # Search bar container
        search_container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        search_container.set_margin_start(8)
        search_container.set_margin_end(8)
        search_container.set_margin_top(8)
        search_container.set_margin_bottom(4)

        # Search entry
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_hexpand(True)
        self.search_entry.set_placeholder_text("Search clipboard items...")
        self.search_entry.connect("search-changed", self._on_search_changed)
        self.search_entry.connect("activate", self._on_search_activate)
        search_container.append(self.search_entry)

        main_box.append(search_container)

        # Tag filter area
        tag_frame = Gtk.Frame()
        tag_frame.set_margin_start(8)
        tag_frame.set_margin_end(8)
        tag_frame.set_margin_top(4)
        tag_frame.set_margin_bottom(4)
        tag_frame.add_css_class("view")

        # Minimal tag container - just tags and a small X
        tag_container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        tag_container.set_margin_top(4)
        tag_container.set_margin_bottom(4)
        tag_container.set_margin_start(8)
        tag_container.set_margin_end(8)

        # Scrollable tag area with FlowBox for tag buttons
        tag_scrolled = Gtk.ScrolledWindow()
        tag_scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.NEVER)
        tag_scrolled.set_max_content_height(40)
        tag_scrolled.set_min_content_height(32)
        tag_scrolled.set_propagate_natural_height(True)
        tag_scrolled.set_hexpand(True)

        self.tag_flowbox = Gtk.FlowBox()
        self.tag_flowbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.tag_flowbox.set_homogeneous(False)
        self.tag_flowbox.set_column_spacing(4)
        self.tag_flowbox.set_row_spacing(4)
        self.tag_flowbox.set_max_children_per_line(15)
        tag_scrolled.set_child(self.tag_flowbox)

        tag_container.append(tag_scrolled)

        # Small X button to clear filter
        clear_btn = Gtk.Button()
        clear_btn.set_icon_name("window-close-symbolic")
        clear_btn.add_css_class("flat")
        clear_btn.set_tooltip_text("Clear filter")
        clear_btn.set_valign(Gtk.Align.CENTER)
        # Make it very small
        css_provider = Gtk.CssProvider()
        css_data = "button { min-width: 20px; min-height: 20px; padding: 2px; }"
        css_provider.load_from_data(css_data.encode())
        clear_btn.get_style_context().add_provider(css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        clear_btn.connect("clicked", lambda btn: self._clear_tag_filter())
        tag_container.append(clear_btn)
        tag_frame.set_child(tag_container)

        # Create TabView for Recently Copied and Recently Pasted
        self.tab_view = Adw.TabView()
        self.tab_view.set_vexpand(True)

        # Prevent tabs from being closed by the user
        self.tab_view.connect("close-page", self._on_close_page)

        # Tab bar
        tab_bar = Adw.TabBar()
        tab_bar.set_view(self.tab_view)
        main_box.append(tab_bar)

        # Tab 1: Recently Copied
        copied_scrolled = Gtk.ScrolledWindow()
        copied_scrolled.set_vexpand(True)
        copied_scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.copied_scrolled = copied_scrolled

        copied_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        # Header bar with status and jump to top button
        copied_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        copied_header.set_margin_top(8)
        copied_header.set_margin_bottom(4)
        copied_header.set_margin_start(8)
        copied_header.set_margin_end(8)

        # Status label for copied items
        self.copied_status_label = Gtk.Label()
        self.copied_status_label.add_css_class("dim-label")
        self.copied_status_label.add_css_class("caption")
        self.copied_status_label.set_hexpand(True)
        self.copied_status_label.set_halign(Gtk.Align.START)
        copied_header.append(self.copied_status_label)

        # Jump to top button for copied items
        copied_jump_btn = Gtk.Button()
        copied_jump_btn.set_icon_name("go-top-symbolic")
        copied_jump_btn.set_tooltip_text("Jump to top")
        copied_jump_btn.add_css_class("flat")
        copied_jump_btn.connect("clicked", lambda btn: self._jump_to_top("copied"))
        copied_header.append(copied_jump_btn)

        self.copied_listbox = Gtk.ListBox()
        self.copied_listbox.add_css_class("boxed-list")
        self.copied_listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        copied_box.append(self.copied_listbox)

        # Loader for copied items
        self.copied_loader = self._create_loader()
        self.copied_loader.set_visible(False)
        copied_box.append(self.copied_loader)

        # Footer with status and jump to top (moved to bottom)
        copied_box.append(copied_header)

        copied_scrolled.set_child(copied_box)

        # Connect scroll event for infinite scroll
        copied_vadj = copied_scrolled.get_vadjustment()
        copied_vadj.connect("value-changed", lambda adj: self._on_scroll_changed(adj, "copied"))

        copied_page = self.tab_view.append(copied_scrolled)
        copied_page.set_title("Recently Copied")
        copied_page.set_icon(Gio.ThemedIcon.new("edit-copy-symbolic"))

        # Tab 2: Recently Pasted
        pasted_scrolled = Gtk.ScrolledWindow()
        pasted_scrolled.set_vexpand(True)
        pasted_scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.pasted_scrolled = pasted_scrolled

        pasted_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        # Header bar with status and jump to top button
        pasted_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        pasted_header.set_margin_top(8)
        pasted_header.set_margin_bottom(4)
        pasted_header.set_margin_start(8)
        pasted_header.set_margin_end(8)

        # Status label for pasted items
        self.pasted_status_label = Gtk.Label()
        self.pasted_status_label.add_css_class("dim-label")
        self.pasted_status_label.add_css_class("caption")
        self.pasted_status_label.set_hexpand(True)
        self.pasted_status_label.set_halign(Gtk.Align.START)
        pasted_header.append(self.pasted_status_label)

        # Jump to top button for pasted items
        pasted_jump_btn = Gtk.Button()
        pasted_jump_btn.set_icon_name("go-top-symbolic")
        pasted_jump_btn.set_tooltip_text("Jump to top")
        pasted_jump_btn.add_css_class("flat")
        pasted_jump_btn.connect("clicked", lambda btn: self._jump_to_top("pasted"))
        pasted_header.append(pasted_jump_btn)

        self.pasted_listbox = Gtk.ListBox()
        self.pasted_listbox.add_css_class("boxed-list")
        self.pasted_listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        pasted_box.append(self.pasted_listbox)

        # Loader for pasted items
        self.pasted_loader = self._create_loader()
        self.pasted_loader.set_visible(False)
        pasted_box.append(self.pasted_loader)

        # Footer with status and jump to top (moved to bottom)
        pasted_box.append(pasted_header)

        pasted_scrolled.set_child(pasted_box)

        # Connect scroll event for infinite scroll
        pasted_vadj = pasted_scrolled.get_vadjustment()
        pasted_vadj.connect("value-changed", lambda adj: self._on_scroll_changed(adj, "pasted"))

        pasted_page = self.tab_view.append(pasted_scrolled)
        pasted_page.set_title("Recently Pasted")
        pasted_page.set_icon(Gio.ThemedIcon.new("edit-paste-symbolic"))

        # Tab 3: Settings
        settings_scrolled = Gtk.ScrolledWindow()
        settings_scrolled.set_vexpand(True)
        settings_scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        # Create settings page using PreferencesPage
        settings_page = Adw.PreferencesPage()

        # Display Settings Group
        display_group = Adw.PreferencesGroup()
        display_group.set_title("Display Settings")
        display_group.set_description("Configure how clipboard items are displayed")

        # Item Width setting
        item_width_row = Adw.SpinRow()
        item_width_row.set_title("Item Width")
        item_width_row.set_subtitle("Width of clipboard item cards in pixels (50-1000)")
        item_width_row.set_adjustment(
            Gtk.Adjustment.new(
                value=self.settings.item_width,
                lower=50,
                upper=1000,
                step_increment=10,
                page_increment=50,
                page_size=0
            )
        )
        item_width_row.set_digits(0)
        self.item_width_spin = item_width_row
        display_group.add(item_width_row)

        # Item Height setting
        item_height_row = Adw.SpinRow()
        item_height_row.set_title("Item Height")
        item_height_row.set_subtitle("Height of clipboard item cards in pixels (50-1000)")
        item_height_row.set_adjustment(
            Gtk.Adjustment.new(
                value=self.settings.item_height,
                lower=50,
                upper=1000,
                step_increment=10,
                page_increment=50,
                page_size=0
            )
        )
        item_height_row.set_digits(0)
        self.item_height_spin = item_height_row
        display_group.add(item_height_row)

        # Max Page Length setting
        page_length_row = Adw.SpinRow()
        page_length_row.set_title("Max Page Length")
        page_length_row.set_subtitle("Maximum number of items to load per page (1-100)")
        page_length_row.set_adjustment(
            Gtk.Adjustment.new(
                value=self.settings.max_page_length,
                lower=1,
                upper=100,
                step_increment=1,
                page_increment=10,
                page_size=0
            )
        )
        page_length_row.set_digits(0)
        self.page_length_spin = page_length_row
        display_group.add(page_length_row)

        settings_page.add(display_group)

        # Shortcuts Settings Group
        shortcuts_group = Adw.PreferencesGroup()
        shortcuts_group.set_title("Keyboard Shortcuts")
        shortcuts_group.set_description("Configure global keyboard shortcuts")

        # Show Window shortcut
        shortcut_row = Adw.ActionRow()
        shortcut_row.set_title("Show Window")
        # Escape the shortcut text to prevent markup parsing errors
        escaped_shortcut = GLib.markup_escape_text(self.settings.show_window_shortcut)
        shortcut_row.set_subtitle(f"Current: {escaped_shortcut}")

        # Button to record shortcut
        record_button = Gtk.Button()
        record_button.set_label("Record Shortcut")
        record_button.set_valign(Gtk.Align.CENTER)
        record_button.connect("clicked", self._on_record_shortcut, shortcut_row)
        shortcut_row.add_suffix(record_button)
        self.shortcut_subtitle = shortcut_row  # Store for updating

        shortcuts_group.add(shortcut_row)

        # Reset shortcuts to defaults
        reset_row = Adw.ActionRow()
        reset_row.set_title("Reset Shortcuts")
        reset_row.set_subtitle("Restore default keyboard shortcuts")

        reset_button = Gtk.Button()
        reset_button.set_label("Reset to Defaults")
        reset_button.add_css_class("destructive-action")
        reset_button.set_valign(Gtk.Align.CENTER)
        reset_button.connect("clicked", self._on_reset_shortcuts)
        reset_row.add_suffix(reset_button)

        shortcuts_group.add(reset_row)

        settings_page.add(shortcuts_group)

        # Actions Group (for Save button)
        actions_group = Adw.PreferencesGroup()
        actions_group.set_title("Actions")

        # Create a button row for saving settings
        save_row = Adw.ActionRow()
        save_row.set_title("Save Settings")
        save_row.set_subtitle("Apply changes and save to settings.yml")

        save_button = Gtk.Button()
        save_button.set_label("Apply & Save")
        save_button.add_css_class("suggested-action")
        save_button.set_valign(Gtk.Align.CENTER)
        save_button.connect("clicked", self._on_save_settings)
        save_row.add_suffix(save_button)

        actions_group.add(save_row)
        settings_page.add(actions_group)

        settings_scrolled.set_child(settings_page)

        settings_tab = self.tab_view.append(settings_scrolled)
        settings_tab.set_title("Settings")
        settings_tab.set_icon(Gio.ThemedIcon.new("preferences-system-symbolic"))

        # Tab 4: Tag Manager
        tag_manager_scrolled = Gtk.ScrolledWindow()
        tag_manager_scrolled.set_vexpand(True)
        tag_manager_scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        # Create tag manager page
        tag_manager_page = Adw.PreferencesPage()

        # Tags List Group
        tags_group = Adw.PreferencesGroup()
        tags_group.set_title("User-Defined Tags")
        tags_group.set_description("Manage your custom tags for organizing clipboard items")

        # Add a "Create New Tag" button at the top
        create_tag_row = Adw.ActionRow()
        create_tag_row.set_title("Create New Tag")
        create_tag_row.set_subtitle("Add a new tag to organize your clipboard items")

        create_tag_button = Gtk.Button()
        create_tag_button.set_label("New Tag")
        create_tag_button.add_css_class("suggested-action")
        create_tag_button.set_valign(Gtk.Align.CENTER)
        create_tag_button.connect("clicked", self._on_create_tag)
        create_tag_row.add_suffix(create_tag_button)

        tags_group.add(create_tag_row)
        tag_manager_page.add(tags_group)

        # User tags list group
        self.user_tags_group = Adw.PreferencesGroup()
        self.user_tags_group.set_title("Your Tags")
        tag_manager_page.add(self.user_tags_group)

        tag_manager_scrolled.set_child(tag_manager_page)

        tag_manager_tab = self.tab_view.append(tag_manager_scrolled)
        tag_manager_tab.set_title("Tags")
        tag_manager_tab.set_icon(Gio.ThemedIcon.new("tag-symbolic"))

        # Connect tab switch event
        self.tab_view.connect("notify::selected-page", self._on_tab_switched)

        main_box.append(self.tab_view)

        # Add tag filter at the bottom (footer)
        main_box.append(tag_frame)

        # Set up toast overlay
        self.toast_overlay.set_child(main_box)
        self.set_content(self.toast_overlay)

        # Load clipboard history
        GLib.idle_add(self.load_history)

        # Store current tab state
        self.current_tab = "copied"

        # Search state
        self.search_query = ""
        self.search_timer = None
        self.search_active = False
        self.search_results = []

        # Tag state
        self.all_tags = []  # All available tags (system + user)
        self.selected_tag_ids = []  # Currently selected tag IDs for filtering
        self.tag_buttons = {}  # Dict of tag_id -> button widget
        self.filter_active = False  # Track if tag filtering is active
        self.filtered_items = []  # Filtered items when tag filter is active

        # Position window to the left
        self.position_window_left()

        # Set up global keyboard shortcut
        self.setup_global_shortcut()

        # Load tags for filtering
        self.load_tags()

        # Load user tags for tag manager
        self.load_user_tags()

        logger.info(f"ClipboardWindow initialized in {time.time() - start_time:.2f} seconds")

    def setup_global_shortcut(self):
        """Set up global keyboard shortcut to show/focus window"""
        try:
            # Create action to show/focus window
            show_action = Gio.SimpleAction.new("show-window", None)
            show_action.connect("activate", self._on_show_window_activated)
            self.add_action(show_action)

            # Get application and set accelerator
            app = self.get_application()
            if app:
                shortcut = self.settings.show_window_shortcut
                app.set_accels_for_action("win.show-window", [shortcut])
                print(f"Global shortcut set: {shortcut} -> show window")
        except Exception as e:
            print(f"Error setting up global shortcut: {e}")

    def _on_show_window_activated(self, action, parameter):
        """Callback when show window shortcut is activated"""
        # Present the window (brings to front and focuses)
        self.present()
        print("Window presented via global shortcut")

    def position_window_left(self):
        """Position window to the left side of the screen"""
        display = Gdk.Display.get_default()
        if display:
            surface = self.get_surface()
            if surface:
                # Move to left edge
                surface.toplevel_move(0, 0)

    def load_history(self):
        """Load clipboard history and listen for updates via WebSocket"""
        self.history_load_start_time = time.time()
        logger.info("Starting initial history load...")

        def run_websocket():
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.websocket_client())

        # Run in background thread
        thread = threading.Thread(target=run_websocket, daemon=True)
        thread.start()

    async def websocket_client(self):
        """WebSocket client to connect to backend"""
        uri = "ws://localhost:8765"
        max_size = 5 * 1024 * 1024  # 5MB to match server
        print(f"Connecting to WebSocket server at {uri}...")

        try:
            async with websockets.connect(uri, max_size=max_size) as websocket:
                print("Connected to WebSocket server")

                # Request history
                request = {"action": "get_history", "limit": self.page_size}
                await websocket.send(json.dumps(request))
                print("Requested history")

                # Listen for messages
                async for message in websocket:
                    data = json.loads(message)
                    msg_type = data.get("type")

                    if msg_type == "history":
                        # Initial history load
                        items = data.get("items", [])
                        total_count = data.get("total_count", 0)
                        offset = data.get("offset", 0)
                        print(f"Received {len(items)} items from history (total: {total_count})")
                        GLib.idle_add(self._initial_history_load, items, total_count, offset)

                    elif msg_type == "recently_pasted":
                        # Pasted history load
                        items = data.get("items", [])
                        total_count = data.get("total_count", 0)
                        offset = data.get("offset", 0)
                        print(f"Received {len(items)} pasted items (total: {total_count})")
                        GLib.idle_add(self._initial_pasted_load, items, total_count, offset)

                    elif msg_type == "new_item":
                        # New item added
                        item = data.get("item")
                        if item:
                            print(f"New item received: {item['type']}")
                            GLib.idle_add(self.add_item, item)

                    elif msg_type == "item_deleted":
                        # Item deleted
                        item_id = data.get("id")
                        if item_id:
                            GLib.idle_add(self.remove_item, item_id)

        except websockets.exceptions.ConnectionClosedError:
            # Normal closure when app exits - suppress error
            print("WebSocket connection closed")
        except Exception as e:
            print(f"WebSocket error: {e}")
            traceback.print_exc()
            GLib.idle_add(self.show_error, str(e))

    def load_pasted_history(self):
        """Load recently pasted items via WebSocket"""
        page_size = self.page_size  # Capture for closure

        def run_websocket():
            try:

                async def get_pasted():
                    uri = "ws://localhost:8765"
                    max_size = 5 * 1024 * 1024  # 5MB
                    async with websockets.connect(uri, max_size=max_size) as websocket:
                        # Request pasted history
                        request = {"action": "get_recently_pasted", "limit": page_size}
                        await websocket.send(json.dumps(request))

                        # Wait for response
                        response = await websocket.recv()
                        data = json.loads(response)

                        if data.get("type") == "recently_pasted":
                            items = data.get("items", [])
                            print(f"Received {len(items)} pasted items")
                            GLib.idle_add(self.update_pasted_history, items)

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(get_pasted())

            except Exception as e:
                print(f"Error loading pasted history: {e}")

        # Run in background thread
        thread = threading.Thread(target=run_websocket, daemon=True)
        thread.start()

    def _create_loader(self):
        """Create an animated loader using the TFCBM loader.svg"""
        # Load the animated SVG loader
        loader_path = Path(__file__).parent.parent / "resouces" / "loader.svg"

        if loader_path.exists():
            # Create a Picture widget to display the SVG
            picture = Gtk.Picture.new_for_filename(str(loader_path))
            picture.set_size_request(120, 120)  # SVG is 120x120
            picture.set_halign(Gtk.Align.CENTER)
            picture.set_valign(Gtk.Align.CENTER)
            picture.set_can_shrink(False)
            return picture
        else:
            # Fallback to spinner if SVG not found
            spinner = Gtk.Spinner()
            spinner.set_size_request(24, 24)
            spinner.set_halign(Gtk.Align.CENTER)
            spinner.set_valign(Gtk.Align.CENTER)
            spinner.start()
            return spinner

    def show_toast(self, message):
        """Show a toast notification"""
        toast = Adw.Toast.new(message)
        toast.set_timeout(2)  # 2 seconds
        self.toast_overlay.add_toast(toast)

    def update_history(self, history):
        """Update the copied listbox with history items"""
        # Clear existing items
        while True:
            row = self.copied_listbox.get_row_at_index(0)
            if row is None:
                break
            self.copied_listbox.remove(row)

        # Add items (already in reverse order from backend)
        for item in history:
            row = ClipboardItemRow(item, self)
            self.copied_listbox.prepend(row)  # Add to top

        return False  # Don't repeat

    def update_pasted_history(self, history):
        """Update the pasted listbox with pasted items"""
        # Clear existing items
        while True:
            row = self.pasted_listbox.get_row_at_index(0)
            if row is None:
                break
            self.pasted_listbox.remove(row)

        # Add items (database returns DESC order, append to maintain it)
        for item in history:
            row = ClipboardItemRow(item, self, show_pasted_time=True)
            self.pasted_listbox.append(row)  # Append to maintain DESC order

        return False  # Don't repeat

    def _initial_history_load(self, items, total_count, offset):
        """Initial load of copied history with pagination data"""
        if hasattr(self, "history_load_start_time"):
            duration = time.time() - self.history_load_start_time
            logger.info(f"Initial history loaded in {duration:.2f} seconds")
            del self.history_load_start_time

        # Update pagination state
        self.copied_offset = offset
        self.copied_total = total_count
        self.copied_has_more = (offset + len(items)) < total_count

        # Clear existing items
        while True:
            row = self.copied_listbox.get_row_at_index(0)
            if row is None:
                break
            self.copied_listbox.remove(row)

        # Add items (already in reverse order from backend)
        for item in items:
            row = ClipboardItemRow(item, self)
            self.copied_listbox.prepend(row)  # Add to top

        # Update status label
        current_count = len(items)
        self.copied_status_label.set_label(f"Showing {current_count} of {total_count} items")

        # Kill standalone splash screen and show main window
        subprocess.run(["pkill", "-f", "ui/splash.py"], stderr=subprocess.DEVNULL)
        self.present()

        return False  # Don't repeat

    def _initial_pasted_load(self, items, total_count, offset):
        """Initial load of pasted history with pagination data"""
        # Update pagination state
        self.pasted_offset = offset
        self.pasted_total = total_count
        self.pasted_has_more = (offset + len(items)) < total_count

        # Clear existing items
        while True:
            row = self.pasted_listbox.get_row_at_index(0)
            if row is None:
                break
            self.pasted_listbox.remove(row)

        # Add items (database returns DESC order, append to maintain it)
        for item in items:
            row = ClipboardItemRow(item, self, show_pasted_time=True)
            self.pasted_listbox.append(row)  # Append to maintain DESC order

        # Update status label
        current_count = len(items)
        self.pasted_status_label.set_label(f"Showing {current_count} of {total_count} items")

        # Scroll to top
        vadj = self.pasted_scrolled.get_vadjustment()
        vadj.set_value(0)

        return False  # Don't repeat

    def add_item(self, item):
        """Add a single new item to the top of the copied list"""
        row = ClipboardItemRow(item, self)
        self.copied_listbox.prepend(row)
        # Force the listbox to redraw
        self.copied_listbox.queue_draw()
        # Update the total count
        self.copied_total_count = self.copied_total_count + 1 if hasattr(self, 'copied_total_count') else 1
        self._update_copied_status()
        return False

    def _update_copied_status(self):
        """Update the copied items status label"""
        # Count current items in listbox
        current_count = 0
        index = 0
        while True:
            row = self.copied_listbox.get_row_at_index(index)
            if row is None:
                break
            current_count += 1
            index += 1

        # Update status label
        total = getattr(self, 'copied_total_count', current_count)
        self.copied_status_label.set_label(f"Showing {current_count} of {total} items")

    def remove_item(self, item_id):
        """Remove an item from both lists by ID"""
        # Remove from copied list
        index = 0
        while True:
            row = self.copied_listbox.get_row_at_index(index)
            if row is None:
                break
            if hasattr(row, "item") and row.item.get("id") == item_id:
                self.copied_listbox.remove(row)
                break
            index += 1

        # Remove from pasted list
        index = 0
        while True:
            row = self.pasted_listbox.get_row_at_index(index)
            if row is None:
                break
            if hasattr(row, "item") and row.item.get("id") == item_id:
                self.pasted_listbox.remove(row)
                break
            index += 1

        return False

    def show_error(self, error_msg):
        """Show error message"""
        error_label = Gtk.Label(label=f"Error: {error_msg}")
        error_label.add_css_class("error")
        error_label.set_selectable(True)  # Make error copyable
        error_label.set_wrap(True)
        self.copied_listbox.append(error_label)
        return False

    def _on_tab_switched(self, tab_view, param):
        """Handle tab switching"""
        selected_page = tab_view.get_selected_page()
        if selected_page:
            title = selected_page.get_title()
            if title == "Recently Pasted":
                self.current_tab = "pasted"
                # Reset pagination and reload pasted items from the beginning
                self.pasted_offset = 0
                self.pasted_has_more = True
                # Load pasted items when switching to pasted tab
                GLib.idle_add(self.load_pasted_history)
            else:
                self.current_tab = "copied"

    def _jump_to_top(self, list_type):
        """Scroll to the top of the specified list"""
        if list_type == "copied":
            vadj = self.copied_scrolled.get_vadjustment()
            vadj.set_value(0)
        elif list_type == "pasted":
            vadj = self.pasted_scrolled.get_vadjustment()
            vadj.set_value(0)

    def _on_scroll_changed(self, adjustment, list_type):
        """Handle scroll events for infinite scrolling"""
        if adjustment.get_upper() - adjustment.get_page_size() - adjustment.get_value() < 50: # 50 pixels from bottom
            if list_type == "copied" and self.copied_has_more and not self.copied_loading:
                print("[UI] Scrolled to bottom of copied list, loading more...")
                self.copied_loading = True
                self.copied_loader.set_visible(True)
                GLib.idle_add(self._load_more_copied_items)
            elif list_type == "pasted" and self.pasted_has_more and not self.pasted_loading:
                print("[UI] Scrolled to bottom of pasted list, loading more...")
                self.pasted_loading = True
                self.pasted_loader.set_visible(True)
                GLib.idle_add(self._load_more_pasted_items)

    def _load_more_copied_items(self):
        """Load more copied items via WebSocket"""
        def run_websocket():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._fetch_more_items("copied"))
        threading.Thread(target=run_websocket, daemon=True).start()
        return False

    def _load_more_pasted_items(self):
        """Load more pasted items via WebSocket"""
        def run_websocket():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._fetch_more_items("pasted"))
        threading.Thread(target=run_websocket, daemon=True).start()
        return False

    async def _fetch_more_items(self, list_type):
        """Fetch more items from backend via WebSocket"""
        uri = "ws://localhost:8765"
        max_size = 5 * 1024 * 1024  # 5MB
        try:
            async with websockets.connect(uri, max_size=max_size) as websocket:
                if list_type == "copied":
                    request = {"action": "get_history", "offset": self.copied_offset + self.page_size, "limit": self.page_size}
                else: # pasted
                    request = {"action": "get_recently_pasted", "offset": self.pasted_offset + self.page_size, "limit": self.page_size}
                
                await websocket.send(json.dumps(request))
                response = await websocket.recv()
                data = json.loads(response)

                if data.get("type") == "history" and list_type == "copied":
                    items = data.get("items", [])
                    total_count = data.get("total_count", 0)
                    offset = data.get("offset", 0)
                    GLib.idle_add(self._append_items_to_listbox, items, total_count, offset, "copied")
                elif data.get("type") == "recently_pasted" and list_type == "pasted":
                    items = data.get("items", [])
                    total_count = data.get("total_count", 0)
                    offset = data.get("offset", 0)
                    GLib.idle_add(self._append_items_to_listbox, items, total_count, offset, "pasted")

        except Exception as e:
            print(f"WebSocket error fetching more {list_type} items: {e}")
            traceback.print_exc()
            GLib.idle_add(lambda: self.show_toast(f"Error loading more items: {str(e)}") or False)
        finally:
            if list_type == "copied":
                GLib.idle_add(lambda: self.copied_loader.set_visible(False))
                self.copied_loading = False
            else:
                GLib.idle_add(lambda: self.pasted_loader.set_visible(False))
                self.pasted_loading = False

    def _append_items_to_listbox(self, items, total_count, offset, list_type):
        """Append new items to the respective listbox"""
        if list_type == "copied":
            listbox = self.copied_listbox
            self.copied_offset = offset
            self.copied_total = total_count
            self.copied_has_more = (self.copied_offset + len(items)) < self.copied_total
            self.copied_loader.set_visible(False)
            self.copied_loading = False
        else: # pasted
            listbox = self.pasted_listbox
            self.pasted_offset = offset
            self.pasted_total = total_count
            self.pasted_has_more = (self.pasted_offset + len(items)) < self.pasted_total
            self.pasted_loader.set_visible(False)
            self.pasted_loading = False

        for item in items:
            row = ClipboardItemRow(item, self, show_pasted_time=(list_type == "pasted"))
            listbox.append(row)

        # Count current rows in listbox
        current_count = 0
        index = 0
        while True:
            row = listbox.get_row_at_index(index)
            if row is None:
                break
            current_count += 1
            index += 1

        # Update status label
        if list_type == "copied":
            self.copied_status_label.set_label(f"Showing {current_count} of {self.copied_total} items")
        else:
            self.pasted_status_label.set_label(f"Showing {current_count} of {self.pasted_total} items")

        return False # Don't repeat

    def _on_record_shortcut(self, button, shortcut_row):
        """Record a new keyboard shortcut"""
        button.set_label("Press keys...")
        button.set_sensitive(False)

        # Create event controller to capture key press
        key_controller = Gtk.EventControllerKey.new()

        def on_key_pressed(controller, keyval, keycode, state):
            # Get modifier keys
            modifiers = []
            if state & Gdk.ModifierType.CONTROL_MASK:
                modifiers.append("Control")
            if state & Gdk.ModifierType.ALT_MASK:
                modifiers.append("Alt")
            if state & Gdk.ModifierType.SHIFT_MASK:
                modifiers.append("Shift")
            if state & Gdk.ModifierType.SUPER_MASK:
                modifiers.append("Super")

            # Get key name
            key_name = Gdk.keyval_name(keyval)

            # Build accelerator string
            if modifiers and key_name:
                accel = "<" + "><".join(modifiers) + ">" + key_name
                # Escape the shortcut text to prevent markup parsing errors
                escaped_accel = GLib.markup_escape_text(accel)
                shortcut_row.set_subtitle(f"Current: {escaped_accel}")
                self.new_shortcut = accel

                # Show toast (escaped for display)
                toast = Adw.Toast.new(f"Shortcut set to: {escaped_accel}")
                toast.set_timeout(2)
                self.toast_overlay.add_toast(toast)

            # Cleanup
            button.set_label("Record Shortcut")
            button.set_sensitive(True)
            self.remove_controller(controller)
            return True

        key_controller.connect("key-pressed", on_key_pressed)
        self.add_controller(key_controller)

    def _on_reset_shortcuts(self, button):
        """Reset shortcuts to defaults"""
        default_shortcut = "<Alt>grave"
        # Escape the shortcut text to prevent markup parsing errors
        escaped_default = GLib.markup_escape_text(default_shortcut)
        self.shortcut_subtitle.set_subtitle(f"Current: {escaped_default}")
        self.new_shortcut = default_shortcut

        # Show toast
        toast = Adw.Toast.new("Shortcuts reset to defaults")
        toast.set_timeout(2)
        self.toast_overlay.add_toast(toast)

    def _on_save_settings(self, button):
        """Save settings changes to YAML file and apply them"""
        try:
            # Get values from spin rows
            new_item_width = int(self.item_width_spin.get_value())
            new_item_height = int(self.item_height_spin.get_value())
            new_page_length = int(self.page_length_spin.get_value())

            # Prepare settings update dictionary
            settings_update = {
                'display.item_width': new_item_width,
                'display.item_height': new_item_height,
                'display.max_page_length': new_page_length
            }

            # Add shortcut if it was changed
            if hasattr(self, 'new_shortcut'):
                settings_update['shortcuts.show_window'] = self.new_shortcut

            # Update settings using the settings manager
            self.settings.update_settings(**settings_update)

            # Show success toast
            toast = Adw.Toast.new("Settings saved successfully! Restart the app to apply changes.")
            toast.set_timeout(3)
            self.toast_overlay.add_toast(toast)

            print(f"Settings saved: item_width={new_item_width}, item_height={new_item_height}, max_page_length={new_page_length}")

        except Exception as e:
            # Show error toast
            toast = Adw.Toast.new(f"Error saving settings: {str(e)}")
            toast.set_timeout(5)
            self.toast_overlay.add_toast(toast)
            print(f"Error saving settings: {e}")

    def _on_close_request(self, window):
        """Handle window close request - kill server before exiting"""
        if self.server_pid:
            try:

                print(f"\nKilling server (PID: {self.server_pid})...")
                os.kill(self.server_pid, signal.SIGTERM)

                # Also kill the tee process if it exists

                subprocess.run(["pkill", "-P", str(self.server_pid)], stderr=subprocess.DEVNULL)
            except Exception as e:
                print(f"Error killing server: {e}")

        print("Exiting UI...")
        return False  # Allow window to close

    def _on_close_page(self, tab_view, page):
        """Prevent pages from being closed. This should also hide the close button."""
        logger.info("Intercepted 'close-page' signal. Preventing tab closure.")
        return True  # Returning True handles the signal and prevents the default action (closing)

    def _on_search_changed(self, entry):
        """Handle search entry text changes with 1-second debouncing"""
        # Cancel existing timer if any
        if self.search_timer:
            GLib.source_remove(self.search_timer)
            self.search_timer = None

        query = entry.get_text().strip()

        # If query is empty, clear search and restore normal view
        if not query:
            self.search_query = ""
            self.search_active = False
            self.search_results = []
            self._restore_normal_view()
            return

        # Set up 1-second delay before searching
        self.search_timer = GLib.timeout_add(1000, self._perform_search, query)

    def _on_search_activate(self, entry):
        """Handle Enter key press - search immediately"""
        # Cancel debounce timer
        if self.search_timer:
            GLib.source_remove(self.search_timer)
            self.search_timer = None

        query = entry.get_text().strip()
        if query:
            self._perform_search(query)

    def _perform_search(self, query):
        """Perform the actual search via WebSocket"""
        self.search_query = query
        self.search_timer = None  # Clear timer reference

        print(f"[UI] Searching for: '{query}'")

        def run_search():
            try:
                async def search():
                    uri = "ws://localhost:8765"
                    max_size = 5 * 1024 * 1024  # 5MB
                    async with websockets.connect(uri, max_size=max_size) as websocket:
                        request = {"action": "search", "query": query, "limit": 100}
                        await websocket.send(json.dumps(request))

                        response = await websocket.recv()
                        data = json.loads(response)

                        if data.get("type") == "search_results":
                            items = data.get("items", [])
                            result_count = data.get("count", 0)
                            print(f"[UI] Search results: {result_count} items")
                            GLib.idle_add(self._display_search_results, items, query)

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(search())
            except Exception as e:
                print(f"[UI] Search error: {e}")
                traceback.print_exc()
                GLib.idle_add(lambda: self.show_toast(f"Search error: {str(e)}") or False)

        threading.Thread(target=run_search, daemon=True).start()
        return False  # Don't repeat timer

    def _display_search_results(self, items, query):
        """Display search results in the current tab"""
        self.search_active = True
        self.search_results = items

        # Determine which listbox to update based on current tab
        if self.current_tab == "pasted":
            listbox = self.pasted_listbox
            status_label = self.pasted_status_label
            show_pasted_time = True
        else:  # copied
            listbox = self.copied_listbox
            status_label = self.copied_status_label
            show_pasted_time = False

        # Clear existing items
        while True:
            row = listbox.get_row_at_index(0)
            if row is None:
                break
            listbox.remove(row)

        # Display search results or empty message
        if items:
            for item in items:
                row = ClipboardItemRow(item, self, show_pasted_time=show_pasted_time)
                listbox.append(row)
            status_label.set_label(f"Search: {len(items)} results for '{query}'")
        else:
            # Show empty results message
            empty_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            empty_box.set_valign(Gtk.Align.CENTER)
            empty_box.set_margin_top(60)
            empty_box.set_margin_bottom(60)

            empty_label = Gtk.Label(label="No results found")
            empty_label.add_css_class("title-2")
            empty_box.append(empty_label)

            hint_label = Gtk.Label(label=f"No clipboard items match '{query}'")
            hint_label.add_css_class("dim-label")
            empty_box.append(hint_label)

            listbox.append(empty_box)
            status_label.set_label(f"Search: 0 results for '{query}'")

        return False

    def _restore_normal_view(self):
        """Restore normal view when search is cleared"""
        # Reset pagination and reload current tab
        if self.current_tab == "pasted":
            self.pasted_offset = 0
            self.pasted_has_more = True
            GLib.idle_add(self.load_pasted_history)
        else:  # copied
            # Reload first page of copied items
            def reload_copied():
                try:
                    async def get_history():
                        uri = "ws://localhost:8765"
                        max_size = 5 * 1024 * 1024
                        async with websockets.connect(uri, max_size=max_size) as websocket:
                            request = {"action": "get_history", "limit": self.page_size}
                            await websocket.send(json.dumps(request))
                            response = await websocket.recv()
                            data = json.loads(response)

                            if data.get("type") == "history":
                                items = data.get("items", [])
                                total_count = data.get("total_count", 0)
                                offset = data.get("offset", 0)
                                GLib.idle_add(self._initial_history_load, items, total_count, offset)

                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(get_history())
                except Exception as e:
                    print(f"[UI] Error reloading history: {e}")

            threading.Thread(target=reload_copied, daemon=True).start()

    # ========== Tag Methods ==========

    def load_tags(self):
        """Load tags from server via WebSocket"""
        self.tags_load_start_time = time.time()
        logger.info("Starting tags load...")
        def run_load():
            try:
                async def fetch_tags():
                    uri = "ws://localhost:8765"
                    async with websockets.connect(uri) as websocket:
                        request = {"action": "get_tags"}
                        await websocket.send(json.dumps(request))

                        response = await websocket.recv()
                        data = json.loads(response)

                        if data.get("type") == "tags":
                            tags = data.get("tags", [])
                            # Add system tags based on item types
                            system_tags = [
                                {"id": "system_text", "name": "Text", "color": "#3584e4", "is_system": True},
                                {"id": "system_image", "name": "Image", "color": "#33d17a", "is_system": True},
                                {"id": "system_screenshot", "name": "Screenshot", "color": "#e01b24", "is_system": True},
                            ]
                            all_tags = system_tags + tags
                            GLib.idle_add(self._update_tags, all_tags)

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(fetch_tags())
            except Exception as e:
                print(f"[UI] Error loading tags: {e}")

        threading.Thread(target=run_load, daemon=True).start()

    def _update_tags(self, tags):
        """Update tags in UI thread"""
        if hasattr(self, "tags_load_start_time"):
            duration = time.time() - self.tags_load_start_time
            logger.info(f"Tags loaded in {duration:.2f} seconds")
            del self.tags_load_start_time
        self.all_tags = tags
        self._refresh_tag_display()

    def _refresh_tag_display(self):
        """Refresh the tag display area"""
        # Clear existing tags
        while True:
            child = self.tag_flowbox.get_first_child()
            if not child:
                break
            self.tag_flowbox.remove(child)

        self.tag_buttons = {}

        # Add tag buttons
        for tag in self.all_tags:
            tag_id = tag.get("id")
            tag_name = tag.get("name", "")
            tag_color = tag.get("color", "#9a9996")
            is_selected = tag_id in self.selected_tag_ids

            # Create button for tag
            btn = Gtk.Button.new_with_label(tag_name)
            btn.add_css_class("pill")

            # Apply color styling - selected tags colored, unselected greyed out
            css_provider = Gtk.CssProvider()
            if is_selected:
                css_data = f"button.pill {{ background-color: alpha({tag_color}, 0.25); color: {tag_color}; font-size: 9pt; font-weight: normal; padding: 2px 8px; min-height: 20px; border: 1px solid alpha({tag_color}, 0.4); border-radius: 2px; }}"
            else:
                # Unselected: greyed out
                css_data = "button.pill { background-color: alpha(#666666, 0.08); color: alpha(#666666, 0.5); font-size: 9pt; font-weight: normal; padding: 2px 8px; min-height: 20px; border: 1px solid alpha(#666666, 0.2); border-radius: 2px; }"
            css_provider.load_from_data(css_data.encode())
            btn.get_style_context().add_provider(
                css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

            btn.connect("clicked", lambda b, tid=tag_id: self._on_tag_clicked(tid))

            self.tag_buttons[tag_id] = btn
            self.tag_flowbox.append(btn)

    def _on_tag_clicked(self, tag_id):
        """Handle tag button click - toggle selection"""
        if tag_id in self.selected_tag_ids:
            self.selected_tag_ids.remove(tag_id)
        else:
            self.selected_tag_ids.append(tag_id)

        # Refresh display to update button styles
        self._refresh_tag_display()

        # Apply filter if tags are selected
        if self.selected_tag_ids:
            self._apply_tag_filter()
        else:
            self._restore_filtered_view()

    def _clear_tag_filter(self):
        """Clear all tag filters"""
        self.selected_tag_ids = []
        self._refresh_tag_display()
        self._restore_filtered_view()

    def _apply_tag_filter(self):
        """Filter items by selected tags at UI level (no DB calls)"""
        print(f"[UI] Applying tag filter: {self.selected_tag_ids}")

        if not self.selected_tag_ids:
            self._restore_normal_view()
            return

        # Map system tag IDs to item types
        type_map = {
            "system_text": ["text"],
            "system_image": ["image/generic", "image/file", "image/web", "image/screenshot"],
            "system_screenshot": ["image/screenshot"]
        }

        # Get user-defined tag IDs (non-system tags) - convert to string to check
        user_tag_ids = [tag_id for tag_id in self.selected_tag_ids if not str(tag_id).startswith("system_")]

        # Get allowed types from system tags
        allowed_types = []
        for tag_id in self.selected_tag_ids:
            if tag_id in type_map:
                allowed_types.extend(type_map[tag_id])

        # Determine which listbox to update
        if self.current_tab == "pasted":
            listbox = self.pasted_listbox
        else:
            listbox = self.copied_listbox

        # Filter rows by showing/hiding them based on tags
        visible_count = 0
        i = 0
        while True:
            row = listbox.get_row_at_index(i)
            if not row:
                break

            if hasattr(row, 'item'):
                item = row.item
                item_type = item.get('type', '')
                item_tags = item.get('tags', [])

                # Extract tag IDs from item tags
                item_tag_ids = [tag.get('id') for tag in item_tags if isinstance(tag, dict)]

                # Check if item matches filter
                matches = False

                # If we have system tag filters, check type match
                if allowed_types:
                    if item_type in allowed_types:
                        # If we also have user tags, check if item has those tags
                        if user_tag_ids:
                            # Item must have at least one of the selected user tags
                            if any(tag_id in item_tag_ids for tag_id in user_tag_ids):
                                matches = True
                        else:
                            # No user tags, just type match is enough
                            matches = True

                # If we only have user tag filters (no system tags)
                elif user_tag_ids:
                    if any(tag_id in item_tag_ids for tag_id in user_tag_ids):
                        matches = True

                # Show/hide row based on match
                row.set_visible(matches)
                if matches:
                    visible_count += 1

            i += 1

        self.filter_active = True
        self.show_toast(f"Showing {visible_count} filtered items")

    def _restore_filtered_view(self):
        """Restore normal unfiltered view by making all rows visible"""
        if not self.filter_active:
            return

        self.filter_active = False

        # Determine which listbox to update
        if self.current_tab == "pasted":
            listbox = self.pasted_listbox
        else:
            listbox = self.copied_listbox

        # Show all rows again
        i = 0
        while True:
            row = listbox.get_row_at_index(i)
            if not row:
                break
            row.set_visible(True)
            i += 1

    # ========== Tag Manager Methods ==========

    def load_user_tags(self):
        """Load user-defined tags for the tag manager"""
        self.user_tags_load_start_time = time.time()
        logger.info("Starting user tags load...")
        def run_load():
            try:
                async def fetch_tags():
                    uri = "ws://localhost:8765"
                    async with websockets.connect(uri) as websocket:
                        request = {"action": "get_tags"}
                        await websocket.send(json.dumps(request))

                        response = await websocket.recv()
                        data = json.loads(response)

                        if data.get("type") == "tags":
                            tags = data.get("tags", [])
                            # Only user-defined tags (not system tags)
                            GLib.idle_add(self._refresh_user_tags_display, tags)

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(fetch_tags())
            except Exception as e:
                print(f"[UI] Error loading user tags: {e}")

        threading.Thread(target=run_load, daemon=True).start()

    def _refresh_user_tags_display(self, tags):
        """Refresh the user tags display in the tag manager"""
        if hasattr(self, "user_tags_load_start_time"):
            duration = time.time() - self.user_tags_load_start_time
            logger.info(f"User tags loaded in {duration:.2f} seconds")
            del self.user_tags_load_start_time
        # Clear existing tags - AdwPreferencesGroup stores rows internally
        # We need to track and remove only the rows we added
        if hasattr(self, '_user_tag_rows'):
            for row in self._user_tag_rows:
                self.user_tags_group.remove(row)

        self._user_tag_rows = []

        # Add tag rows
        if not tags:
            empty_row = Adw.ActionRow()
            empty_row.set_title("No custom tags yet")
            empty_row.set_subtitle("Create your first tag to organize clipboard items")
            self.user_tags_group.add(empty_row)
            self._user_tag_rows.append(empty_row)
        else:
            for tag in tags:
                tag_id = tag.get("id")
                tag_name = tag.get("name", "")
                tag_color = tag.get("color", "#9a9996")

                tag_row = Adw.ActionRow()
                tag_row.set_title(tag_name)

                # Create a color indicator box
                color_box = Gtk.Box()
                color_box.set_size_request(20, 20)
                color_box.add_css_class("card")

                # Apply color
                css_provider = Gtk.CssProvider()
                css_data = f"box {{ background-color: {tag_color}; border-radius: 4px; }}"
                css_provider.load_from_data(css_data.encode())
                color_box.get_style_context().add_provider(
                    css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                )
                tag_row.add_prefix(color_box)

                # Edit button
                edit_button = Gtk.Button()
                edit_button.set_icon_name("document-edit-symbolic")
                edit_button.set_valign(Gtk.Align.CENTER)
                edit_button.add_css_class("flat")
                edit_button.connect("clicked", lambda b, tid=tag_id: self._on_edit_tag(tid))
                tag_row.add_suffix(edit_button)

                # Delete button
                delete_button = Gtk.Button()
                delete_button.set_icon_name("user-trash-symbolic")
                delete_button.set_valign(Gtk.Align.CENTER)
                delete_button.add_css_class("flat")
                delete_button.add_css_class("destructive-action")
                delete_button.connect("clicked", lambda b, tid=tag_id: self._on_delete_tag(tid))
                tag_row.add_suffix(delete_button)

                self.user_tags_group.add(tag_row)
                self._user_tag_rows.append(tag_row)

    def _on_create_tag(self, button):
        """Show dialog to create a new tag"""
        dialog = Adw.MessageDialog.new(self)
        dialog.set_heading("Create New Tag")
        dialog.set_body("Enter a name for the new tag")

        # Create entry for tag name
        entry_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        entry_box.set_margin_top(12)
        entry_box.set_margin_bottom(12)
        entry_box.set_margin_start(12)
        entry_box.set_margin_end(12)

        name_entry = Gtk.Entry()
        name_entry.set_placeholder_text("Tag name")
        entry_box.append(name_entry)

        # Color picker - use a simple dropdown with predefined colors
        color_label = Gtk.Label()
        color_label.set_text("Choose a color:")
        color_label.set_halign(Gtk.Align.START)
        entry_box.append(color_label)

        color_flow = Gtk.FlowBox()
        color_flow.set_selection_mode(Gtk.SelectionMode.SINGLE)
        color_flow.set_max_children_per_line(6)
        color_flow.set_column_spacing(6)
        color_flow.set_row_spacing(6)

        colors = ["#3584e4", "#33d17a", "#f6d32d", "#ff7800", "#e01b24", "#9141ac", "#986a44", "#5e5c64"]
        for color in colors:
            color_btn = Gtk.Button()
            color_btn.set_size_request(40, 40)
            # Store color value on button for later retrieval
            color_btn.color_value = color
            css_provider = Gtk.CssProvider()
            css_data = f"button {{ background-color: {color}; border-radius: 20px; }}"
            css_provider.load_from_data(css_data.encode())
            color_btn.get_style_context().add_provider(
                css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
            # Make button clickable to select its flowbox child
            def on_color_click(btn, flow=color_flow):
                # Find and select this button's parent FlowBoxChild
                parent = btn.get_parent()
                if parent:
                    flow.select_child(parent)
            color_btn.connect("clicked", on_color_click)
            color_flow.append(color_btn)

        color_flow.select_child(color_flow.get_child_at_index(0))
        entry_box.append(color_flow)

        dialog.set_extra_child(entry_box)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("create", "Create")
        dialog.set_response_appearance("create", Adw.ResponseAppearance.SUGGESTED)

        def on_response(dialog, response):
            if response == "create":
                tag_name = name_entry.get_text().strip()
                if not tag_name:
                    self.show_toast("Tag name cannot be empty")
                    return

                # Get selected color from the selected FlowBoxChild's button
                selected = color_flow.get_selected_children()
                if selected and len(selected) > 0:
                    # Get the button from the FlowBoxChild
                    flow_child = selected[0]
                    button = flow_child.get_child()
                    if hasattr(button, 'color_value'):
                        selected_color = button.color_value
                    else:
                        selected_color = colors[0]
                else:
                    selected_color = colors[0]

                # Create tag via WebSocket
                self._create_tag_on_server(tag_name, selected_color)

        dialog.connect("response", on_response)
        dialog.present()

    def _create_tag_on_server(self, name, color):
        """Create a new tag on the server"""
        def run_create():
            try:
                async def create_tag():
                    print(f"[UI] Creating tag: name='{name}', color='{color}'")
                    uri = "ws://localhost:8765"
                    async with websockets.connect(uri) as websocket:
                        request = {
                            "action": "create_tag",
                            "name": name,
                            "color": color
                        }
                        print(f"[UI] Sending create_tag request: {request}")
                        await websocket.send(json.dumps(request))

                        response = await websocket.recv()
                        data = json.loads(response)
                        print(f"[UI] Received response: {data}")

                        if data.get("type") == "tag_created":
                            print(f"[UI] Tag created successfully")
                            GLib.idle_add(self.show_toast, f"Tag '{name}' created")
                            GLib.idle_add(self.load_user_tags)
                            GLib.idle_add(self.load_tags)  # Refresh tag filter display
                        else:
                            print(f"[UI] Tag creation failed - unexpected response type: {data.get('type')}")
                            GLib.idle_add(self.show_toast, f"Failed to create tag: {data.get('message', 'Unknown error')}")

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(create_tag())
            except Exception as e:
                print(f"[UI] Exception creating tag: {e}")
                import traceback
                traceback.print_exc()
                GLib.idle_add(self.show_toast, f"Error creating tag: {e}")

        threading.Thread(target=run_create, daemon=True).start()

    def _on_edit_tag(self, tag_id):
        """Show dialog to edit a tag"""
        # Find the tag
        tag = None
        for t in self.all_tags:
            if t.get("id") == tag_id and not t.get("is_system"):
                tag = t
                break

        if not tag:
            self.show_toast("Tag not found")
            return

        dialog = Adw.MessageDialog.new(self)
        dialog.set_heading("Edit Tag")
        dialog.set_body(f"Modify the tag '{tag.get('name')}'")

        # Create entry for tag name
        entry_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        entry_box.set_margin_top(12)
        entry_box.set_margin_bottom(12)
        entry_box.set_margin_start(12)
        entry_box.set_margin_end(12)

        name_entry = Gtk.Entry()
        name_entry.set_text(tag.get("name", ""))
        entry_box.append(name_entry)

        # Color picker
        color_label = Gtk.Label()
        color_label.set_text("Choose a color:")
        color_label.set_halign(Gtk.Align.START)
        entry_box.append(color_label)

        color_flow = Gtk.FlowBox()
        color_flow.set_selection_mode(Gtk.SelectionMode.SINGLE)
        color_flow.set_max_children_per_line(6)
        color_flow.set_column_spacing(6)
        color_flow.set_row_spacing(6)

        colors = ["#3584e4", "#33d17a", "#f6d32d", "#ff7800", "#e01b24", "#9141ac", "#986a44", "#5e5c64"]
        current_color_index = 0
        if tag.get("color") in colors:
            current_color_index = colors.index(tag.get("color"))

        for color in colors:
            color_btn = Gtk.Button()
            color_btn.set_size_request(40, 40)
            # Store color value on button
            color_btn.color_value = color
            css_provider = Gtk.CssProvider()
            css_data = f"button {{ background-color: {color}; border-radius: 20px; }}"
            css_provider.load_from_data(css_data.encode())
            color_btn.get_style_context().add_provider(
                css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
            # Make button clickable to select its flowbox child
            def on_color_click(btn, flow=color_flow):
                parent = btn.get_parent()
                if parent:
                    flow.select_child(parent)
            color_btn.connect("clicked", on_color_click)
            color_flow.append(color_btn)

        color_flow.select_child(color_flow.get_child_at_index(current_color_index))
        entry_box.append(color_flow)

        dialog.set_extra_child(entry_box)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("save", "Save")
        dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)

        def on_response(dialog, response):
            if response == "save":
                tag_name = name_entry.get_text().strip()
                if not tag_name:
                    self.show_toast("Tag name cannot be empty")
                    return

                # Get selected color from the selected FlowBoxChild's button
                selected = color_flow.get_selected_children()
                if selected and len(selected) > 0:
                    flow_child = selected[0]
                    button = flow_child.get_child()
                    if hasattr(button, 'color_value'):
                        selected_color = button.color_value
                    else:
                        selected_color = colors[current_color_index]
                else:
                    selected_color = colors[current_color_index]

                # Update tag via WebSocket
                self._update_tag_on_server(tag_id, tag_name, selected_color)

        dialog.connect("response", on_response)
        dialog.present()

    def _update_tag_on_server(self, tag_id, name, color):
        """Update a tag on the server"""
        def run_update():
            try:
                async def update_tag():
                    uri = "ws://localhost:8765"
                    async with websockets.connect(uri) as websocket:
                        request = {
                            "action": "update_tag",
                            "tag_id": tag_id,
                            "name": name,
                            "color": color
                        }
                        await websocket.send(json.dumps(request))

                        response = await websocket.recv()
                        data = json.loads(response)

                        if data.get("type") == "tag_updated":
                            GLib.idle_add(self.show_toast, f"Tag updated")
                            GLib.idle_add(self.load_user_tags)
                            GLib.idle_add(self.load_tags)  # Refresh tag filter display
                        else:
                            GLib.idle_add(self.show_toast, "Failed to update tag")

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(update_tag())
            except Exception as e:
                print(f"[UI] Error updating tag: {e}")
                GLib.idle_add(self.show_toast, f"Error updating tag: {e}")

        threading.Thread(target=run_update, daemon=True).start()

    def _on_delete_tag(self, tag_id):
        """Show confirmation dialog and delete tag"""
        # Find the tag
        tag = None
        for t in self.all_tags:
            if t.get("id") == tag_id:
                tag = t
                break

        if not tag:
            self.show_toast("Tag not found")
            return

        dialog = Adw.MessageDialog.new(self)
        dialog.set_heading("Delete Tag")
        dialog.set_body(f"Are you sure you want to delete the tag '{tag.get('name')}'?")
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("delete", "Delete")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)

        def on_response(dialog, response):
            if response == "delete":
                self._delete_tag_on_server(tag_id)

        dialog.connect("response", on_response)
        dialog.present()

    def _delete_tag_on_server(self, tag_id):
        """Delete a tag on the server"""
        def run_delete():
            try:
                async def delete_tag():
                    uri = "ws://localhost:8765"
                    async with websockets.connect(uri) as websocket:
                        request = {
                            "action": "delete_tag",
                            "tag_id": tag_id
                        }
                        await websocket.send(json.dumps(request))

                        response = await websocket.recv()
                        data = json.loads(response)

                        if data.get("type") == "tag_deleted":
                            GLib.idle_add(self.show_toast, "Tag deleted")
                            GLib.idle_add(self.load_user_tags)
                            GLib.idle_add(self.load_tags)  # Refresh tag filter display
                        else:
                            GLib.idle_add(self.show_toast, "Failed to delete tag")

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(delete_tag())
            except Exception as e:
                print(f"[UI] Error deleting tag: {e}")
                GLib.idle_add(self.show_toast, f"Error deleting tag: {e}")

        threading.Thread(target=run_delete, daemon=True).start()


class ClipboardApp(Adw.Application):
    """Main application"""

    def __init__(self, server_pid=None):
        super().__init__(application_id="org.tfcbm.ClipboardManager")
        self.server_pid = server_pid

    def do_startup(self):
        """Application startup - set icon"""
        Adw.Application.do_startup(self)

        # Set default window icon list for the application
        try:
            icon_path = Path(__file__).parent.parent / "resouces" / "icon.svg"
            if icon_path.exists():
                # Load icon as pixbuf and set as default
                pixbuf = GdkPixbuf.Pixbuf.new_from_file(str(icon_path))
                # GTK4 uses textures, convert pixbuf to texture
                Gdk.Texture.new_for_pixbuf(pixbuf)
                # Set icon for the display
                display = Gdk.Display.get_default()
                if display:
                    icon_theme = Gtk.IconTheme.get_for_display(display)
                    # Add the resources directory to icon search path
                    icon_theme.add_search_path(str(icon_path.parent))
        except Exception as e:
            print(f"Warning: Could not set up application icon: {e}")

        # Load custom CSS
        try:
            css_path = Path(__file__).parent / "style.css"
            if css_path.exists():
                provider = Gtk.CssProvider()
                provider.load_from_path(str(css_path))
                Gtk.StyleContext.add_provider_for_display(
                    Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                )
                print(f"Loaded custom CSS from {css_path}")
        except Exception as e:
            print(f"Warning: Could not load custom CSS: {e}")

    def do_activate(self):
        """Activate the application"""
        win = self.props.active_window
        if not win:
            # Create main window (splash.py is already running from load.sh)
            win = ClipboardWindow(self, self.server_pid)
            # Window will be shown after history loads and kills the standalone splash
        else:
            win.present()


def main():
    """Entry point"""

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="TFCBM UI")
    parser.add_argument("--server-pid", type=int, help="Server process ID to kill on exit")
    args = parser.parse_args()

    # Log startup
    logger.info("TFCBM UI starting...")
    if args.server_pid:
        logger.info(f"Monitoring server PID: {args.server_pid}")

    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        if args.server_pid:
            try:

                print(f"\n\nKilling server (PID: {args.server_pid})...")
                os.kill(args.server_pid, signal.SIGTERM)

                # Also kill child processes

                subprocess.run(["pkill", "-P", str(args.server_pid)], stderr=subprocess.DEVNULL)
            except Exception as e:
                print(f"Error killing server: {e}")
        print("Shutting down UI...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    app = ClipboardApp(args.server_pid)
    try:
        return app.run(None)
    except KeyboardInterrupt:
        if args.server_pid:
            try:

                print(f"\n\nKilling server (PID: {args.server_pid})...")
                os.kill(args.server_pid, signal.SIGTERM)
            except Exception as e:
                print(f"Error killing server: {e}")
        print("\n\nShutting down UI...")
        sys.exit(0)


if __name__ == "__main__":
    main()
