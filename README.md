# TFCBM - The F*cking Clipboard Manager

A clipboard history manager for GNOME Wayland that actually works.

## How It Works

This uses a **two-part solution** to work around GNOME Wayland's clipboard security:

1.  **GNOME Shell Extension** (GJS) - Runs inside GNOME Shell with clipboard access, monitors changes, and sends them to the Python server.
2.  **Python Server** - Receives clipboard data via a UNIX socket, processes it, and logs it.

## Quick Start

The `load.sh` script automates the entire setup process.

1.  **Clone the repository (if you haven't already):**
    ```bash
    git clone <repository_url>
    cd TFCBM
    ```

2.  **Run the loader script:**
    ```bash
    ./load.sh
    ```
    This will install all dependencies (system, Python, npm), set up the environment, and start the server in the background.

3.  **Restart GNOME Shell:**
    To activate the extension, you need to restart your GNOME Shell. On Wayland, the easiest way is to **log out and log back in**.

4.  **Done!**
    The server is now running in the background. To see the real-time log of clipboard events, run:
    ```bash
    tail -f tfcbm_server.log
    ```

## Available Scripts

-   `load.sh`: The all-in-one script. Installs all dependencies, installs the GNOME extension, and starts the server in the background.
-   `install.sh`: Installs all dependencies and the GNOME extension. Does not start the server.
-   `install_extension.sh`: Installs only the GNOME extension and its npm dependencies.

## Features

- ✓ Event-driven clipboard monitoring.
- ✓ Differentiates content sources (file, web, screenshot).
- ✓ Text and image clipboard support.
- ✓ Automatic screenshot capture (configurable).
- ✓ Works on GNOME Wayland.
- ✓ Simple UNIX socket IPC.

## Troubleshooting

-   **Extension not loading?**
    Check if it's enabled with `gnome-extensions list --enabled | grep simple-clipboard`.
    View detailed logs with `journalctl -f /usr/bin/gnome-shell`.

-   **Server not running?**
    Check if the server is running with `pgrep -f tfcbm_server.py`.
    If not, you can start it with `./load.sh` or manually with `python3 tfcbm_server.py`.
    Check the server logs with `tail -f tfcbm_server.log`.

## Screenshot Feature

Screenshots are automatically captured every 30 seconds and added to clipboard history.

**Configure in tfcbm_server.py:**
```python
SCREENSHOT_INTERVAL = 30  # seconds between screenshots
SCREENSHOT_ENABLED = False  # Set to True to enable
SCREENSHOT_SAVE_DIR = None  # Set to a directory path to save screenshots
```

See **SCREENSHOT_FEATURE.md** for full documentation.

## Future Ideas

- [ ] Save history to disk (JSON export)
- [ ] GUI for browsing history
- [ ] Clipboard search
- [ ] D-Bus interface instead of UNIX socket
- [ ] History size limits
- [ ] Screenshot area/window selection

## License

Do whatever you want with it.
