#!/usr/bin/env python3
"""
TFCBM UI - GTK4 clipboard manager interface
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Adw, GLib, Gdk, GdkPixbuf, Gio
import json
import base64
import threading
import signal
import sys
import asyncio
import websockets
from pathlib import Path


class ClipboardItemRow(Gtk.ListBoxRow):
    """A row displaying a single clipboard item (text or image)"""

    def __init__(self, item, window):
        super().__init__()
        self.item = item
        self.window = window

        # Make row activatable (clickable)
        self.set_activatable(True)
        self.connect('activate', self._on_row_clicked)

        # Main box for the row
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        main_box.set_margin_start(12)
        main_box.set_margin_end(12)
        main_box.set_margin_top(8)
        main_box.set_margin_bottom(8)

        # Header box with timestamp and buttons
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        # Timestamp label
        timestamp = item.get('timestamp', '')
        if timestamp:
            time_label = Gtk.Label(label=self._format_timestamp(timestamp))
            time_label.add_css_class('dim-label')
            time_label.add_css_class('caption')
            time_label.set_halign(Gtk.Align.START)
            time_label.set_hexpand(True)
            header_box.append(time_label)

        # Button box
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)

        # Save button (with event controller to stop propagation)
        save_button = Gtk.Button()
        save_button.set_icon_name('document-save-symbolic')
        save_button.add_css_class('flat')
        save_button.set_tooltip_text('Save to file')

        # Use click gesture to stop propagation
        save_gesture = Gtk.GestureClick.new()
        save_gesture.connect('released', lambda g, n, x, y: self._do_save())
        save_gesture.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        save_button.add_controller(save_gesture)
        button_box.append(save_button)

        # Delete button (with event controller to stop propagation)
        delete_button = Gtk.Button()
        delete_button.set_icon_name('user-trash-symbolic')
        delete_button.add_css_class('flat')
        delete_button.set_tooltip_text('Delete item')

        # Use click gesture to stop propagation
        delete_gesture = Gtk.GestureClick.new()
        delete_gesture.connect('released', lambda g, n, x, y: self._on_delete_clicked(delete_button))
        delete_gesture.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        delete_button.add_controller(delete_gesture)
        button_box.append(delete_button)

        header_box.append(button_box)
        main_box.append(header_box)

        # Content box
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        # Make content box clickable to copy (works on background, not on selectable text)
        content_gesture = Gtk.GestureClick.new()
        content_gesture.connect('released', lambda g, n, x, y: self._on_row_clicked(self))
        box.add_controller(content_gesture)

        # Content based on type
        if item['type'] == 'text':
            content_label = Gtk.Label(label=item['content'])
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

        elif item['type'].startswith('image/') or item['type'] == 'screenshot':
            try:
                # Use thumbnail if available, otherwise use full image
                thumbnail_data = item.get('thumbnail')
                image_data_b64 = thumbnail_data if thumbnail_data else item['content']

                print(f"[UI] Loading image item {item.get('id')}, type: {item['type']}")
                print(f"[UI] Has thumbnail: {bool(thumbnail_data)}, data length: {len(image_data_b64) if image_data_b64 else 0}")

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
                image_gesture.connect('released', lambda g, n, x, y: self._on_row_clicked(self))
                picture.add_controller(image_gesture)

                # Add cursor to indicate clickable
                picture.set_cursor(Gdk.Cursor.new_from_name("pointer"))

                box.append(picture)
                print(f"[UI] ✓ Image widget added to UI")

                # Add image type label
                type_label = Gtk.Label(label=f"[{item['type']}]")
                type_label.add_css_class('dim-label')
                type_label.add_css_class('caption')
                type_label.set_halign(Gtk.Align.START)
                box.append(type_label)

            except Exception as e:
                error_label = Gtk.Label(label=f"Failed to load image: {str(e)}")
                error_label.add_css_class('error')
                error_label.set_selectable(True)  # Make error copyable
                error_label.set_wrap(True)
                box.append(error_label)

        main_box.append(box)
        self.set_child(main_box)

    def _format_timestamp(self, timestamp_str):
        """Format ISO timestamp to readable format"""
        from datetime import datetime
        try:
            dt = datetime.fromisoformat(timestamp_str)
            return dt.strftime('%H:%M:%S')
        except:
            return timestamp_str

    def _on_row_clicked(self, row):
        """Copy item to clipboard when row is clicked"""
        item_type = self.item['type']

        clipboard = Gdk.Display.get_default().get_clipboard()

        if item_type == 'text':
            content = self.item['content']
            clipboard.set(content)
            print(f"Copied text to clipboard: {content[:50]}")
            # Show toast notification
            self.window.show_toast("Text copied to clipboard")

        elif item_type.startswith('image/') or item_type == 'screenshot':
            # For images, use thumbnail for copying (it's already in memory)
            thumbnail_data = self.item.get('thumbnail')
            if thumbnail_data:
                try:
                    # Decode base64 thumbnail
                    image_data = base64.b64decode(thumbnail_data)
                    loader = GdkPixbuf.PixbufLoader()
                    loader.write(image_data)
                    loader.close()
                    pixbuf = loader.get_pixbuf()

                    # Use texture with ContentProvider for GTK4/Wayland
                    texture = Gdk.Texture.new_for_pixbuf(pixbuf)
                    content = Gdk.ContentProvider.new_for_value(texture)
                    clipboard.set_content(content)
                    print(f"Copied image to clipboard")
                    # Show toast notification with image icon
                    self.window.show_toast("📷 Image copied to clipboard")
                except Exception as e:
                    print(f"Error copying image: {e}")
                    import traceback
                    traceback.print_exc()
                    self.window.show_toast(f"Error: {str(e)}")
            else:
                print("No thumbnail available to copy")
                self.window.show_toast("No image available")

    def _on_save_clicked(self, button):
        """Save item to file - stop event propagation"""
        # Stop the click from activating the row
        return True

    def _do_save(self):
        """Actually perform the save"""
        item_type = self.item['type']
        item_id = self.item['id']

        # Create file chooser dialog
        dialog = Gtk.FileDialog()

        if item_type == 'text':
            dialog.set_initial_name('clipboard.txt')
        elif item_type.startswith('image/'):
            ext = item_type.split('/')[-1]
            dialog.set_initial_name(f'clipboard.{ext}')
        elif item_type == 'screenshot':
            dialog.set_initial_name('screenshot.png')

        # Get the window
        window = self.get_root()

        def on_save_finish(dialog, result):
            try:
                file = dialog.save_finish(result)
                if file:
                    path = file.get_path()

                    if item_type == 'text':
                        content = self.item['content']
                        with open(path, 'w') as f:
                            f.write(content)
                        print(f"Saved text to {path}")
                    elif item_type.startswith('image/') or item_type == 'screenshot':
                        # For images, request full image from server
                        self._save_full_image(item_id, path)

            except Exception as e:
                print(f"Error saving file: {e}")

        dialog.save(window, None, on_save_finish)

    def _save_full_image(self, item_id, path):
        """Request and save full image from server"""
        def fetch_and_save():
            try:
                import asyncio
                import websockets

                async def get_full_image():
                    uri = "ws://localhost:8765"
                    async with websockets.connect(uri) as websocket:
                        # Request full image
                        request = {'action': 'get_full_image', 'id': item_id}
                        await websocket.send(json.dumps(request))

                        # Wait for response
                        response = await websocket.recv()
                        data = json.loads(response)

                        if data.get('type') == 'full_image' and data.get('id') == item_id:
                            image_b64 = data.get('content')
                            image_data = base64.b64decode(image_b64)

                            # Save to file
                            with open(path, 'wb') as f:
                                f.write(image_data)

                            print(f"Saved full image to {path}")

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(get_full_image())

            except Exception as e:
                print(f"Error fetching full image: {e}")

        # Run in background thread
        import threading
        thread = threading.Thread(target=fetch_and_save, daemon=True)
        thread.start()

    def _on_delete_clicked(self, button):
        """Delete item with confirmation"""
        window = self.get_root()

        # Create confirmation dialog
        dialog = Adw.AlertDialog.new(
            "Delete this item?",
            "This item will be permanently removed from your clipboard history."
        )

        dialog.add_response("cancel", "Nah")
        dialog.add_response("delete", "Yeah")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        def on_response(dialog, response):
            if response == "delete":
                # Send delete request via WebSocket
                self._delete_item_from_server(self.item['id'])

        dialog.connect("response", on_response)
        dialog.present(window)

    def _delete_item_from_server(self, item_id):
        """Send delete request to server via WebSocket"""
        def send_delete():
            try:
                import asyncio
                import websockets

                async def delete_item():
                    uri = "ws://localhost:8765"
                    async with websockets.connect(uri) as websocket:
                        # Send delete request
                        request = {'action': 'delete_item', 'id': item_id}
                        await websocket.send(json.dumps(request))
                        print(f"Deleted item {item_id}")

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(delete_item())

            except Exception as e:
                print(f"Error deleting item: {e}")

        # Run in background thread
        import threading
        thread = threading.Thread(target=send_delete, daemon=True)
        thread.start()


class ClipboardWindow(Adw.ApplicationWindow):
    """Main application window"""

    def __init__(self, app, server_pid=None):
        super().__init__(application=app, title="TFCBM")

        self.server_pid = server_pid

        # Connect close request handler
        self.connect('close-request', self._on_close_request)

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
            icon_path = Path(__file__).parent.parent / 'resouces' / 'tfcbm-256.png'
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
        settings_button.set_icon_name('emblem-system-symbolic')
        settings_button.add_css_class('flat')
        header.pack_end(settings_button)

        main_box.append(header)

        # Scrolled window for clipboard items
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        # ListBox for items
        self.listbox = Gtk.ListBox()
        self.listbox.add_css_class('boxed-list')
        self.listbox.set_selection_mode(Gtk.SelectionMode.NONE)

        scrolled.set_child(self.listbox)
        main_box.append(scrolled)

        # Set up toast overlay
        self.toast_overlay.set_child(main_box)
        self.set_content(self.toast_overlay)

        # Load clipboard history
        GLib.idle_add(self.load_history)

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
                request = {'action': 'get_history', 'limit': 100}
                await websocket.send(json.dumps(request))
                print("Requested history")

                # Listen for messages
                async for message in websocket:
                    data = json.loads(message)
                    msg_type = data.get('type')

                    if msg_type == 'history':
                        # Initial history load
                        items = data.get('items', [])
                        print(f"Received {len(items)} items from history")
                        GLib.idle_add(self.update_history, items)

                    elif msg_type == 'new_item':
                        # New item added
                        item = data.get('item')
                        if item:
                            print(f"New item received: {item['type']}")
                            GLib.idle_add(self.add_item, item)

                    elif msg_type == 'item_deleted':
                        # Item deleted
                        item_id = data.get('id')
                        if item_id:
                            GLib.idle_add(self.remove_item, item_id)

        except Exception as e:
            print(f"WebSocket error: {e}")
            import traceback
            traceback.print_exc()
            GLib.idle_add(self.show_error, str(e))

    def show_toast(self, message):
        """Show a toast notification"""
        toast = Adw.Toast.new(message)
        toast.set_timeout(2)  # 2 seconds
        self.toast_overlay.add_toast(toast)

    def update_history(self, history):
        """Update the listbox with history items"""
        # Clear existing items
        while True:
            row = self.listbox.get_row_at_index(0)
            if row is None:
                break
            self.listbox.remove(row)

        # Add items (already in reverse order from backend)
        for item in history:
            row = ClipboardItemRow(item, self)
            self.listbox.prepend(row)  # Add to top

        return False  # Don't repeat

    def add_item(self, item):
        """Add a single new item to the top of the list"""
        row = ClipboardItemRow(item, self)
        self.listbox.prepend(row)
        return False

    def remove_item(self, item_id):
        """Remove an item from the list by ID"""
        # Find and remove the row with matching ID
        index = 0
        while True:
            row = self.listbox.get_row_at_index(index)
            if row is None:
                break
            if hasattr(row, 'item') and row.item.get('id') == item_id:
                self.listbox.remove(row)
                break
            index += 1
        return False

    def show_error(self, error_msg):
        """Show error message"""
        error_label = Gtk.Label(label=f"Error: {error_msg}")
        error_label.add_css_class('error')
        error_label.set_selectable(True)  # Make error copyable
        error_label.set_wrap(True)
        self.listbox.append(error_label)
        return False

    def _on_close_request(self, window):
        """Handle window close request - kill server before exiting"""
        if self.server_pid:
            try:
                import os
                import signal
                print(f"\nKilling server (PID: {self.server_pid})...")
                os.kill(self.server_pid, signal.SIGTERM)

                # Also kill the tee process if it exists
                import subprocess
                subprocess.run(['pkill', '-P', str(self.server_pid)],
                             stderr=subprocess.DEVNULL)
            except Exception as e:
                print(f"Error killing server: {e}")

        print("Exiting UI...")
        return False  # Allow window to close


class ClipboardApp(Adw.Application):
    """Main application"""

    def __init__(self, server_pid=None):
        super().__init__(application_id='org.tfcbm.ClipboardManager')
        self.server_pid = server_pid

    def do_startup(self):
        """Application startup - set icon"""
        Adw.Application.do_startup(self)

        # Set default window icon list for the application
        try:
            icon_path = Path(__file__).parent.parent / 'resouces' / 'icon.svg'
            if icon_path.exists():
                # Load icon as pixbuf and set as default
                pixbuf = GdkPixbuf.Pixbuf.new_from_file(str(icon_path))
                # GTK4 uses textures, convert pixbuf to texture
                texture = Gdk.Texture.new_for_pixbuf(pixbuf)
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
    import argparse

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='TFCBM UI')
    parser.add_argument('--server-pid', type=int, help='Server process ID to kill on exit')
    args = parser.parse_args()

    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        if args.server_pid:
            try:
                import os
                print(f"\n\nKilling server (PID: {args.server_pid})...")
                os.kill(args.server_pid, signal.SIGTERM)

                # Also kill child processes
                import subprocess
                subprocess.run(['pkill', '-P', str(args.server_pid)],
                             stderr=subprocess.DEVNULL)
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
                import os
                print(f"\n\nKilling server (PID: {args.server_pid})...")
                os.kill(args.server_pid, signal.SIGTERM)
            except Exception as e:
                print(f"Error killing server: {e}")
        print("\n\nShutting down UI...")
        sys.exit(0)


if __name__ == '__main__':
    main()
