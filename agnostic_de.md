# Plan for Making TFCBM Desktop Environment Agnostic

This document outlines the plan to make the TFCBM application independent of any specific Desktop Environment (DE), particularly GNOME. The goal is to ensure the application is compatible with a wide range of Linux distributions and DEs like KDE, XFCE, etc., while preserving all existing functionality.

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
  - **Technology:** We will use the `pyperclip` library for clipboard access. It's a cross-platform library that works on X11-based environments (using `xclip` or `xsel`) and has some support for Wayland.
  - **Wayland Support:** To improve Wayland compatibility, we will also consider using the `pyclip` library, which can use the `wl-clipboard` utility.
  - **Implementation:** A background Python script will poll the clipboard for changes and send a notification to the main application when a change is detected.

- **Global Keyboard Shortcuts:**
  - **Technology:** We will use the `pynput` library to listen for global keyboard shortcuts.
  - **Implementation:** A separate background Python script will listen for the configured shortcut. When the shortcut is pressed, it will send a signal to the main application to toggle its visibility.

- **Settings:**
  - **Technology:** We will replace `GSettings` with a simple JSON file for storing settings (e.g., `~/.config/tfcbm/settings.json`).
  - **Implementation:** The application will read and write its settings from this JSON file. This is a simple and portable solution.

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
- **Add New Dependencies:** The new Python dependencies (`pyperclip`, `pynput`, `pyclip`) will be added to the manifest.
- **Add CLI Tools:** The manifest will be updated to ensure that `xclip`, `xsel`, and `wl-clipboard` are included in the Flatpak runtime to support clipboard access on X11 and Wayland.
- **Update Build and Install Steps:** The build and install commands will be updated to correctly install the new background services and the main application.

## 4. Implementation Steps

The migration will be performed in the following steps:

1.  **Implement the background services:**
    - Create the Python script for clipboard monitoring using `pyperclip` and/or `pyclip`.
    - Create the Python script for global shortcut handling using `pynput`.
    - Implement the IPC mechanism for communication between the background services and the UI.
2.  **Refactor the UI:**
    - Replace `Adw.Application` with `Gtk.Application`.
    - Replace `Adw` widgets with their corresponding GTK4 widgets.
    - Remove the code that checks for and communicates with the GNOME extension.
    - Implement the client side of the IPC mechanism to receive notifications from the background services.
    - Update the settings management to use the new JSON-based settings.
3.  **Update the Flatpak manifest:**
    - Modify the `io.github.dyslechtchitect.tfcbm.yml` file as described above.
4.  **Testing:**
    - Thoroughly test the application on different DEs (GNOME, KDE, XFCE) to ensure that all functionalities are working as expected.
