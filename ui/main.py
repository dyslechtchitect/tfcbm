#!/usr/bin/env python3
"""
TFCBM UI - GTK4 clipboard manager interface
"""

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

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

import websockets
from gi.repository import Adw, Gdk, GdkPixbuf, Gio, GLib, Gtk


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
        main_box.set_margin_start(12)
        main_box.set_margin_end(12)
        main_box.set_margin_top(8)
        main_box.set_margin_bottom(8)

        # Header box with timestamp and buttons
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

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
            time_label.set_hexpand(True)
            header_box.append(time_label)

        # Button box
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)

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

        # Make content box clickable to copy (works on background, not on selectable text)
        content_gesture = Gtk.GestureClick.new()
        content_gesture.connect("released", lambda g, n, x, y: self._on_row_clicked(self))
        box.add_controller(content_gesture)

        # Content based on type
        if item["type"] == "text":
            content_label = Gtk.Label(label=item["content"])
            content_label.set_wrap(True)
            content_label.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
            content_label.set_halign(Gtk.Align.START)
            content_label.set_xalign(0)
            content_label.set_max_width_chars(40)
            content_label.set_selectable(True)

            # Add some padding around text to make background more clickable
            content_label.set_margin_start(8)
            content_label.set_margin_end(8)
            content_label.set_margin_top(4)
            content_label.set_margin_bottom(4)

            box.append(content_label)

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
                picture.set_halign(Gtk.Align.START)
                # Ensure image is displayed at its natural size
                picture.set_can_shrink(False)
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
        self.set_child(main_box)

    def _format_timestamp(self, timestamp_str):
        """Format ISO timestamp to readable format"""

        try:
            dt = datetime.fromisoformat(timestamp_str)
            return dt.strftime("%H:%M:%S")
        except BaseException:
            return timestamp_str

    def _on_row_clicked(self, row):
        """Copy item to clipboard when row is clicked"""
        item_type = self.item["type"]
        item_id = self.item["id"]

        clipboard = Gdk.Display.get_default().get_clipboard()

        if item_type == "text":
            content = self.item["content"]
            clipboard.set(content)
            print(f"Copied text to clipboard: {content[:50]}")
            # Show toast notification
            self.window.show_toast("Text copied to clipboard")
            # Record paste event
            self._record_paste(item_id)

        elif item_type.startswith("image/") or item_type == "screenshot":
            # For images, fetch full image from server then copy to clipboard
            self.window.show_toast("Loading full image...")
            self._copy_full_image_to_clipboard(item_id, clipboard)

    def _copy_full_image_to_clipboard(self, item_id, clipboard):
        """Request and copy full image from server to clipboard"""

        def fetch_and_copy():
            try:

                async def get_full_image():
                    uri = "ws://localhost:8765"
                    async with websockets.connect(uri) as websocket:
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
                            def copy_to_clipboard():
                                try:
                                    # Set the pixbuf directly on clipboard
                                    # This is the most compatible way for applications like GIMP
                                    clipboard.set(pixbuf)

                                    print(
                                        f"Copied full image to clipboard ({pixbuf.get_width()}x{pixbuf.get_height()})"
                                    )
                                    self.window.show_toast(
                                        f"📷 Full image copied ({pixbuf.get_width()}x{pixbuf.get_height()})"
                                    )

                                    # Record paste event
                                    self._record_paste(item_id)
                                except Exception as e:
                                    print(f"Error copying to clipboard: {e}")

                                    traceback.print_exc()
                                    self.window.show_toast(f"Error copying: {str(e)}")
                                return False

                            GLib.idle_add(copy_to_clipboard)

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
                    elif item_type.startswith("image/") or item_type == "screenshot":
                        # For images, request full image from server
                        self._save_full_image(item_id, path)

            except Exception as e:
                print(f"Error saving file: {e}")

        dialog.save(window, None, on_save_finish)

    def _save_full_image(self, item_id, path):
        """Request and save full image from server"""

        def fetch_and_save():
            try:

                async def get_full_image():
                    uri = "ws://localhost:8765"
                    async with websockets.connect(uri) as websocket:
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

    def _on_delete_clicked(self, button):
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
                self._delete_item_from_server(self.item["id"])

        dialog.connect("response", on_response)
        dialog.present(window)

    def _delete_item_from_server(self, item_id):
        """Send delete request to server via WebSocket"""

        def send_delete():
            try:

                async def delete_item():
                    uri = "ws://localhost:8765"
                    async with websockets.connect(uri) as websocket:
                        # Send delete request
                        request = {"action": "delete_item", "id": item_id}
                        await websocket.send(json.dumps(request))
                        print(f"Deleted item {item_id}")

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(delete_item())

            except Exception as e:
                print(f"Error deleting item: {e}")

        # Run in background thread

        thread = threading.Thread(target=send_delete, daemon=True)
        thread.start()

    def _record_paste(self, item_id):
        """Record that this item was pasted (with debouncing to prevent duplicates)"""

        # Debounce: Only record if at least 500ms has passed since last paste
        current_time = time.time()
        if current_time - self._last_paste_time < 0.5:
            print(f"Debouncing duplicate paste for item {item_id}")
            return
        self._last_paste_time = current_time

        def send_record():
            try:

                async def record():
                    uri = "ws://localhost:8765"
                    async with websockets.connect(uri) as websocket:
                        request = {"action": "record_paste", "id": item_id}
                        await websocket.send(json.dumps(request))
                        print(f"Recorded paste for item {item_id}")

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(record())

            except Exception as e:
                print(f"Error recording paste: {e}")

        # Run in background thread

        thread = threading.Thread(target=send_record, daemon=True)
        thread.start()


class ClipboardWindow(Adw.ApplicationWindow):
    """Main application window"""

    def __init__(self, app, server_pid=None):
        super().__init__(application=app, title="TFCBM")

        self.server_pid = server_pid

        # Connect close request handler
        self.connect("close-request", self._on_close_request)

        # Set window properties
        self.set_default_size(350, 800)

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
            icon_path = Path(__file__).parent.parent / "resouces" / "icon-256.png"
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

        self.copied_listbox = Gtk.ListBox()
        self.copied_listbox.add_css_class("boxed-list")
        self.copied_listbox.set_selection_mode(Gtk.SelectionMode.NONE)

        copied_scrolled.set_child(self.copied_listbox)

        copied_page = self.tab_view.append(copied_scrolled)
        copied_page.set_title("Recently Copied")
        copied_page.set_icon(Gio.ThemedIcon.new("edit-copy-symbolic"))

        # Tab 2: Recently Pasted
        pasted_scrolled = Gtk.ScrolledWindow()
        pasted_scrolled.set_vexpand(True)
        pasted_scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.pasted_listbox = Gtk.ListBox()
        self.pasted_listbox.add_css_class("boxed-list")
        self.pasted_listbox.set_selection_mode(Gtk.SelectionMode.NONE)

        pasted_scrolled.set_child(self.pasted_listbox)

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
        print(f"Connecting to WebSocket server at {uri}...")

        try:
            async with websockets.connect(uri) as websocket:
                print("Connected to WebSocket server")

                # Request history
                request = {"action": "get_history", "limit": 100}
                await websocket.send(json.dumps(request))
                print("Requested history")

                # Listen for messages
                async for message in websocket:
                    data = json.loads(message)
                    msg_type = data.get("type")

                    if msg_type == "history":
                        # Initial history load
                        items = data.get("items", [])
                        print(f"Received {len(items)} items from history")
                        GLib.idle_add(self.update_history, items)

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

        def run_websocket():
            try:

                async def get_pasted():
                    uri = "ws://localhost:8765"
                    async with websockets.connect(uri) as websocket:
                        # Request pasted history
                        request = {"action": "get_recently_pasted", "limit": 100}
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
                # Load pasted items when switching to pasted tab
                GLib.idle_add(self.load_pasted_history)
            else:
                self.current_tab = "copied"

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

    def do_activate(self):
        """Activate the application"""
        win = self.props.active_window
        if not win:
            win = ClipboardWindow(self, self.server_pid)
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
