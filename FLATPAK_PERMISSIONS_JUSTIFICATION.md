# Flatpak Permissions Justification for TFCBM

This document provides justification for the permissions requested by TFCBM (The F* Clipboard Manager) for Flathub submission.

## Application Overview

TFCBM is a clipboard manager for GNOME that provides:
- Clipboard history tracking
- Support for text, images, and files
- GNOME Shell extension integration for system-wide clipboard monitoring
- WebSocket-based IPC between UI and backend server

## Permissions and Justifications

### 1. Session Bus Access (`--socket=session-bus`)

**Permission**: `--socket=session-bus`

**Justification**:
TFCBM requires session bus access for the following legitimate reasons:

1. **GNOME Shell Extension Communication**: The app communicates with its GNOME Shell extension via DBus to receive clipboard change notifications. The extension sends events to the app using the DBus interface `io.github.dyslechtchitect.tfcbm`.

2. **Own DBus Name**: The application needs to own the DBus name `io.github.dyslechtchitect.tfcbm` for the extension to communicate with it.

3. **Desktop Notifications**: System notifications for clipboard events.

**Code References**:
- `server/src/dbus_service.py`: Implements DBus service for extension communication
- `gnome-extension/src/adapters/DBusNotifier.js`: Extension-side DBus communication
- `gnome-extension/extension.js`: Main extension that monitors clipboard and sends events

**Specific Services Used**:
- `org.gnome.Shell` - GNOME Shell integration
- `org.freedesktop.portal.Desktop` - Desktop portal for clipboard access
- `org.freedesktop.Flatpak` - For extension installation (see below)
- `io.github.dyslechtchitect.tfcbm` - Own service for extension communication

**Alternative Considered**: Using only specific `--talk-name` permissions was considered, but the dynamic nature of clipboard monitoring and the need to own a DBus name requires session bus access.

### 2. Flatpak Portal Access (`--talk-name=org.freedesktop.Flatpak`)

**Permission**: `--talk-name=org.freedesktop.Flatpak`

**Justification**:
This permission enables `flatpak-spawn --host` functionality, which is **essential** for installing the GNOME Shell extension from within the Flatpak sandbox.

**Why This Is Needed**:
1. GNOME Shell extensions must be installed on the **host system**, not inside the Flatpak sandbox
2. The extension provides seamless clipboard monitoring integration with GNOME Shell
3. The installation is **user-initiated** and **interactive** - users must explicitly run the `tfcbm-install-extension` command

**How It's Used**:
The app includes a script (`tfcbm-install-extension`) that:
1. Detects if running in Flatpak
2. Uses `flatpak-spawn --host` to run `gnome-extensions install` on the host
3. Prompts the user for confirmation before installation
4. Provides clear feedback and next steps

**Code Reference**:
- `io.github.dyslechtchitect.tfcbm.yml` lines 147-211: Extension installer script
- The script checks for existing installation and asks for user confirmation
- Uses only the `gnome-extensions` command for installation (standard GNOME tool)

**Security Considerations**:
- Installation is opt-in and user-initiated
- Only runs standard GNOME extension installation commands
- Does not execute arbitrary code
- Extension is packaged as a zip file within the Flatpak

### 3. Portal Talk-Name Access

**Permissions**:
- `--talk-name=org.freedesktop.portal.Desktop`

**Justification**:
Required for proper clipboard access through the XDG Desktop Portal, which is the sandboxed way to access clipboard content.

### 4. GNOME Shell Access

**Permission**: `--talk-name=org.gnome.Shell`

**Justification**:
Enables integration with GNOME Shell for:
- Detecting if the extension is installed/enabled
- Checking extension status
- Providing user feedback about extension state

**Code Reference**:
- `ui/utils/extension_check.py`: Checks extension status using `gnome-extensions` commands

### 5. Network Access (`--share=network`)

**Permission**: `--share=network`

**Justification**:
TFCBM uses a WebSocket server for IPC between the backend (which manages the clipboard database) and the UI (GTK4 application).

**Architecture**:
- Backend server: `main.py` - Manages clipboard database, WebSocket server
- UI client: `ui/main.py` - GTK4 interface, connects to WebSocket server
- This architecture separates concerns and allows the backend to run independently

**Code References**:
- `main.py`: WebSocket server implementation
- `ui/windows/clipboard_window.py`: WebSocket client for receiving clipboard updates

**Why Not Use Unix Sockets**: The current architecture predates Flatpak packaging and uses WebSockets for cross-platform compatibility.

## Removed Permissions

The following permission was **removed** as it was not actually needed:

- ~~`--system-talk-name=org.freedesktop.DBus`~~ - System bus access is not required for clipboard operations

## Summary

All permissions are **legitimate and necessary** for TFCBM's functionality:

1. **Session bus** - Required for GNOME Shell extension communication and owning DBus service
2. **Flatpak access** - Essential for user-initiated GNOME extension installation
3. **Portal access** - Standard way to access clipboard in sandboxed app
4. **GNOME Shell** - Check extension status and integration
5. **Network** - WebSocket IPC between backend and UI components

The app follows best practices:
- User-initiated actions (extension installation requires explicit user action)
- Clear feedback and prompts
- No arbitrary code execution
- Uses standard GNOME tools only

## Questions or Concerns

If reviewers have questions or concerns about any permission, please ask in the submission PR. We're happy to provide additional details or make changes if there are alternative approaches that achieve the same functionality.

---

**Maintainer**: dyslechtchitect
**Repository**: https://github.com/dyslechtchitect/TFCBM
**Submission Date**: 2025-01-XX
