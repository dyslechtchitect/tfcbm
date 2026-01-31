# Plan for Making TFCBM Desktop Environment Agnostic

This document outlines the plan to make the TFCBM application independent of any specific Desktop Environment (DE), particularly GNOME. The goal is to ensure the application is compatible with a wide range of Linux distributions and DEs like KDE, XFCE, etc., while preserving all existing functionality.

**Target test environments:** Fedora KDE (primary dev), Fedora GNOME, Fedora XFCE

## 1. Analysis of Existing GNOME Dependencies

The application currently has the following hard dependencies on the GNOME ecosystem:

### 1.1. GNOME Shell Extension

A GNOME Shell extension (`gnome-extension`) is used for core functionalities that require integration with the desktop shell.

- **Clipboard Monitoring:** The extension uses `St.Clipboard` from the GNOME Shell toolkit to monitor clipboard changes. This is a GNOME-specific implementation.
- **Global Keyboard Shortcuts:** The extension uses `Main.wm.addKeybinding` to register a global shortcut for showing/hiding the application window. This is a GNOME Shell Window Manager API.
- **Settings:** The extension uses `GSettings` for configuration, which is a GNOME-specific settings storage system.

### 1.2. User Interface (UI)

The UI is built using `libadwaita`, the GNOME HIG toolkit.

- **UI Toolkit:** The main application class inherits from `Adw.Application`, and the UI is built with `Adw` widgets. This results in a UI that looks native only on GNOME.
- **Extension Dependency:** The UI has a hard dependency on the GNOME extension. It checks for the extension's presence and communicates with it for clipboard monitoring and shortcuts.

## 2. Migration Strategy

To make the application DE-agnostic, the following changes will be implemented:

### 2.1. Replace the GNOME Shell Extension

The GNOME Shell extension will be replaced with a Python-based background service that will be shipped with the application. This service will handle clipboard monitoring and global shortcuts in a DE-agnostic way.

- **Clipboard Monitoring:**
  - **Technology:** We will use GTK4's built-in `Gdk.Clipboard` API for clipboard access. It works on both X11 and Wayland across all GTK-supporting DEs. A polling approach (250ms interval) will detect clipboard changes, matching the current extension behavior.
  - **Implementation:** The clipboard monitor will run within the UI process as a GLib timeout, polling for clipboard changes and forwarding events to the server via the existing IPC mechanism.

- **Global Keyboard Shortcuts:**
  - **Technology:** We will use the `pynput` library to listen for global keyboard shortcuts.
  - **Implementation:** A separate background Python script will listen for the configured shortcut. When the shortcut is pressed, it will send a signal to the main application to toggle its visibility.

- **Settings:**
  - **Technology:** We will replace `GSettings` with a simple JSON file for storing settings (e.g., `~/.config/tfcbm/settings.json`).
  - **Implementation:** The application will read and write its settings from this JSON file. This is a simple and portable solution. (Already partially implemented.)

### 2.2. Decouple the UI from GNOME

The UI will be modified to remove its dependency on `libadwaita` and the GNOME extension.

- **UI Toolkit:**
  - **Recommendation:** The recommended approach is to rewrite the UI using standard **GTK4 widgets** instead of `libadwaita` components. This will allow the application to run on any DE that has GTK4 installed, and it will use the system's GTK theme.
  - **Alternative:** A more involved but potentially better long-term solution is to migrate the UI to a different toolkit like **Qt (with PyQt or PySide)**. Qt provides a more consistent look and feel across different DEs. For this plan, we will proceed with the **GTK4** recommendation.

- **Remove Extension Dependency:**
  - The UI will be updated to communicate with the new Python-based background services for clipboard monitoring and shortcuts. This communication can be implemented using a local IPC mechanism like a Unix socket or a local DBus connection.

- **Settings:**
  - The UI will be updated to use the new JSON-based settings storage.

## 3. Update the Flatpak Manifest

The Flatpak manifest (`io.github.dyslechtchitect.tfcbm.yml`) will be updated to reflect the new architecture.

- **Remove GNOME Extension:** The build and install steps for the GNOME Shell extension will be removed.
- **Add New Dependencies:** The new Python dependencies (`pynput`) will be added to the manifest.
- **Update Build and Install Steps:** The build and install commands will be updated to correctly install the new background services and the main application.

## 4. Implementation Checklist

### Step 1: Implement background clipboard monitoring
- [x] Create `ui/services/clipboard_monitor.py` - GTK4-based clipboard polling service
- [x] Integrate clipboard monitor into `clipboard_app.py` (start on activation, replaces extension forwarding)
- [x] Remove extension-based clipboard event forwarding from `clipboard_app.py`

### Step 2: Create JSON-based settings store for shortcuts
- [x] Create `ui/infrastructure/json_settings_store.py` implementing `ISettingsStore`
- [x] Store keyboard shortcut in `~/.config/tfcbm/settings.json`

### Step 3: Refactor UI - Remove libadwaita dependency
- [x] `clipboard_app.py`: Replace `Adw.Application` with `Gtk.Application`
- [x] `clipboard_window.py`: Replace `Adw.ApplicationWindow` with `Gtk.ApplicationWindow`
- [x] `main_window_builder.py`: Replace `Adw.HeaderBar` with `Gtk.HeaderBar`
- [x] `main_window_builder.py`: Replace `Adw.TabView`/`Adw.TabBar` with `Gtk.Notebook`
- [x] `main_window_builder.py`: Replace `Adw.PreferencesGroup` with GTK4 equivalents
- [x] `settings_page.py`: Replace all `Adw` widgets with GTK4 equivalents
- [x] `about.py`: Replace `Adw.AboutDialog` with `Gtk.AboutDialog`
- [x] `clipboard_window.py`: Replace `Adw.MessageDialog` with `Gtk.MessageDialog`
- [x] `extension_error_window.py`: No longer referenced (can be removed)
- [x] `item_dialog_handler.py`: Replace `Adw.AlertDialog` and `Adw.Window` with GTK4 equivalents
- [x] `item_secret_manager.py`: Replace `Adw.AlertDialog` with `Gtk.MessageDialog`
- [x] `secret_naming_dialog.py`: Replace `Adw.AlertDialog` with `Gtk.MessageDialog`
- [x] `tag_dialog_manager.py`: Replace `Adw.MessageDialog` with `Gtk.MessageDialog`
- [x] `user_tags_manager.py`: Replace `Adw.ActionRow` and `Adw.MessageDialog` with GTK4 equivalents
- [x] `clipboard_item_row.py`: Remove Adw import
- [x] `ui/main.py`: Remove `gi.require_version("Adw", "1")`

### Step 4: Remove GNOME extension dependency
- [x] Remove extension check from `clipboard_app.py` startup flow
- [x] Remove `ExtensionSettingsStore` usage from `clipboard_app.py`
- [x] Update `settings_page.py` to use JSON settings store instead of GSettings/extension D-Bus
- [x] Update `shortcut_service.py` to remove extension readiness checks
- [x] Update D-Bus service (`dbus_service.py`) to keep Activate/ShowSettings/Quit but clipboard events now come from internal monitor

### Step 5: Update build and packaging
- [x] Update `meson.build` to remove GNOME extension bundling and install script
- [x] Update Flatpak manifest (`io.github.dyslechtchitect.tfcbm.yml`) - no changes needed, org.gnome.Platform provides GTK4 for all DEs
- [x] Update wrapper script (`tfcbm-wrapper.sh`) - no changes needed, already DE-agnostic

### Step 6: Testing
- [ ] Test on Fedora KDE (current development environment)
- [ ] Test on Fedora GNOME
- [ ] Test on Fedora XFCE
