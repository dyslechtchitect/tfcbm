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


class ClipboardItemRow(Gtk.ListBoxRow):
    """A row displaying a single clipboard item (text or image)"""

    def __init__(self, item, window, show_pasted_time=False):
        super().__init__()
        self.item = item
        self.window = window
        self.show_pasted_time = show_pasted_time
        self._last_paste_time = 0  # Track last paste to prevent duplicates

        # Make row activatable (clickable)
        self.set_activatable(True)
        self.connect("activate", self._on_row_clicked)

        # Main box for the row
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        main_box.set_hexpand(False)  # Prevent horizontal expansion

        # Card frame for styling
        card_frame = Gtk.Frame()
        card_frame.set_vexpand(False)
        card_frame.set_hexpand(False)
        card_frame.set_size_request(200, 200)  # Enforce fixed size
        card_frame.add_css_class("clipboard-item-card")
        card_frame.set_child(main_box)

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

        # Content box
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_hexpand(False)  # Prevent horizontal expansion
        box.add_css_class("clipboard-item-content")  # Add class for content styling

        # Make content box clickable to copy (works on background, not on selectable text)
        content_gesture = Gtk.GestureClick.new()
        content_gesture.connect("released", lambda g, n, x, y: self._on_row_clicked(self))
        box.add_controller(content_gesture)

        # Content based on type
        if item["type"] == "text":
            # Create box for text with big bold quotes
            text_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            text_box.set_halign(Gtk.Align.START)

            # Opening quote - bigger and bold
            open_quote = Gtk.Label(label="\u201c")  # Left double quotation mark
            open_quote.add_css_class("big-quote")
            text_box.append(open_quote)

            # Actual content
            content_label = Gtk.Label(label=item['content'])
            content_label.set_wrap(True)
            content_label.set_ellipsize(Pango.EllipsizeMode.END)
            content_label.set_halign(Gtk.Align.START)
            content_label.add_css_class("clipboard-item-text")
            content_label.add_css_class("typewriter-text")
            content_label.set_selectable(True)
            content_label.set_max_width_chars(40)
            content_label.set_lines(5)
            text_box.append(content_label)

            # Closing quote - bigger and bold
            close_quote = Gtk.Label(label="\u201d")  # Right double quotation mark
            close_quote.add_css_class("big-quote")
            text_box.append(close_quote)

            box.append(text_box)

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

                # Create image widget (thumbnail is already sized correctly)
                texture = Gdk.Texture.new_for_pixbuf(pixbuf)
                picture = Gtk.Picture.new_for_paintable(texture)
                picture.set_halign(Gtk.Align.CENTER)  # Center image
                picture.set_valign(Gtk.Align.CENTER)  # Center image
                picture.add_css_class("clipboard-item-image")  # Apply image styling
                picture.set_content_fit(Gtk.ContentFit.CONTAIN)

                # Make image clickable to copy
                image_gesture = Gtk.GestureClick.new()
                image_gesture.connect("released", lambda g, n, x, y: self._on_row_clicked(self))
                picture.add_controller(image_gesture)

                # Add cursor to indicate clickable
                picture.set_cursor(Gdk.Cursor.new_from_name("pointer"))

                box.append(picture)
                print(f"[UI] ✓ Image widget added to UI")

                # Add image type label
                type_label = Gtk.Label(label=f"[{item['type']}]")
                type_label.add_css_class("dim-label")
                type_label.add_css_class("caption")
                type_label.set_halign(Gtk.Align.START)
                box.append(type_label)

            except Exception as e:
                error_label = Gtk.Label(label=f"Failed to load image: {str(e)}")
                error_label.add_css_class("error")
                error_label.set_selectable(True)  # Make error copyable
                error_label.set_wrap(True)
                box.append(error_label)

        main_box.append(box)
        self.set_child(card_frame)  # Set the card_frame as the child of the row

    def _format_timestamp(self, timestamp_str):
        """Format ISO timestamp to readable format"""

        try:
            dt = datetime.fromisoformat(timestamp_str)
            return dt.strftime("%H:%M:%S")
        except BaseException:
            return timestamp_str

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

                                    # Convert pixbuf to texture for GTK4 clipboard
                                    texture = Gdk.Texture.new_for_pixbuf(pixbuf)
                                    clipboard.set_texture(texture)

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


class ClipboardWindow(Adw.ApplicationWindow):
    """Main application window"""

    def __init__(self, app, server_pid=None):
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

        # Create TabView for Recently Copied and Recently Pasted
        self.tab_view = Adw.TabView()
        self.tab_view.set_vexpand(True)

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

        copied_box.append(copied_header)

        self.copied_listbox = Gtk.ListBox()
        self.copied_listbox.add_css_class("boxed-list")
        self.copied_listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        copied_box.append(self.copied_listbox)

        # Loader for copied items
        self.copied_loader = self._create_loader()
        self.copied_loader.set_visible(False)
        copied_box.append(self.copied_loader)

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

        pasted_box.append(pasted_header)

        self.pasted_listbox = Gtk.ListBox()
        self.pasted_listbox.add_css_class("boxed-list")
        self.pasted_listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        pasted_box.append(self.pasted_listbox)

        # Loader for pasted items
        self.pasted_loader = self._create_loader()
        self.pasted_loader.set_visible(False)
        pasted_box.append(self.pasted_loader)

        pasted_scrolled.set_child(pasted_box)

        # Connect scroll event for infinite scroll
        pasted_vadj = pasted_scrolled.get_vadjustment()
        pasted_vadj.connect("value-changed", lambda adj: self._on_scroll_changed(adj, "pasted"))

        pasted_page = self.tab_view.append(pasted_scrolled)
        pasted_page.set_title("Recently Pasted")
        pasted_page.set_icon(Gio.ThemedIcon.new("edit-paste-symbolic"))

        # Connect tab switch event
        self.tab_view.connect("notify::selected-page", self._on_tab_switched)

        main_box.append(self.tab_view)

        # Set up toast overlay
        self.toast_overlay.set_child(main_box)
        self.set_content(self.toast_overlay)

        # Load clipboard history
        GLib.idle_add(self.load_history)

        # Store current tab state
        self.current_tab = "copied"

        # Position window to the left
        self.position_window_left()

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
        return False

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
