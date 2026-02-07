# DE-Agnostic Architecture: Dependency Changes

This document summarizes all dependency and architectural changes between main and beta branches for Flathub manifest review.

**Summary:** TFCBM no longer requires a GNOME Shell extension. Clipboard monitoring and global shortcuts are now handled in-process using GTK4 and XDG Desktop Portal APIs, making the application desktop-environment agnostic.

---

## Manifest Justification

### Runtime: `org.gnome.Platform`

Required because the application uses GTK4 extensively (`Gtk.Application`, `Gdk.Clipboard`, `Gdk.ContentProvider`, `Gio.File`). The `org.freedesktop.Platform` runtime does not include GTK4—using it would require bundling GTK4 as a module, increasing size and maintenance burden. Despite the name, `org.gnome.Platform` is the standard runtime for any GTK4 Flatpak application, including DE-agnostic ones.

### SDK: `org.gnome.Sdk`

Used only at build time by `flatpak-builder`. It provides Meson, compilers, and headers needed for `buildsystem: meson`. The SDK is never installed on end-user machines—users only receive the runtime. Zero overhead to the shipped Flatpak.

### Finish Args

| Arg | Justification |
|-----|---------------|
| `--share=ipc` | Required for X11 clipboard operations |
| `--socket=wayland` | Primary display protocol |
| `--socket=fallback-x11` | X11 fallback when Wayland unavailable |
| `--device=dri` | GPU acceleration for GTK4 rendering |
| `--filesystem=home:ro` | Required to read file contents when clipboard captures file URIs |

---

## Removed Dependencies

### GNOME Shell Extension (entire `gnome-extension/` directory)

**What it was:**
- 651-line JavaScript extension for GNOME Shell
- Monitored clipboard via GNOME's `St.Clipboard` API
- Forwarded clipboard events to the server via D-Bus
- Handled global keyboard shortcuts via GSettings keybindings

**Why removed:** Extension-based architecture only worked on GNOME. The new architecture handles everything in-process.

**Files removed:**
- `gnome-extension/extension.js` (651 lines)
- `gnome-extension/src/ClipboardMonitorService.js`
- `gnome-extension/src/adapters/GnomeClipboardAdapter.js`
- `gnome-extension/src/adapters/DBusNotifier.js`
- `gnome-extension/metadata.json`
- `gnome-extension/stylesheet.css`
- All test files (1,500+ lines)

### Extension Installation Scripts

| File | Purpose | Why removed |
|------|---------|-------------|
| `tfcbm-install-extension.sh` | Installed extension on host via `flatpak-spawn --host` | No extension to install |
| `build-extension-zip.py` | Built extension zip for distribution | No extension to package |

### Extension Check/Error UI

| File | Purpose | Why removed |
|------|---------|-------------|
| `ui/utils/extension_check.py` (501 lines) | Checked extension installation status | No extension required |
| `ui/windows/extension_error_window.py` (523 lines) | Showed setup instructions when extension missing | No setup needed |

### GSettings Store

**File:** `ui/infrastructure/gsettings_store.py` (629 lines)

**What it was:**
- `GSettingsStore` class for reading/writing shortcuts via GNOME GSettings
- `ExtensionSettingsStore` class for D-Bus communication with extension
- Called extension's `start_monitoring()`, `stop_monitoring()`, `enable_keybinding()`, `disable_keybinding()`

**Why removed:** Required GNOME extension running on host. Not portable to other DEs.

### Libadwaita Dependency



**What it was:**
- `gi.require_version("Adw", "1")` in `ui/main.py`
- `class ClipboardApp(Adw.Application)` base class

**Why removed:** Libadwaita is GNOME-specific theming library. Pure GTK4 is sufficient and more portable.

---דגכדג


קודים קיםדוםדרידםקרדירםדCריגדכעדג

## Added Dependencies

### In-Process Clipboard Monitor

**File:** `ui/services/clipboard_monitor.py` (271 lines)

**What it does:**
- Uses GTK4's `Gdk.Clipboard` with `changed` signal
- Cascading read strategy: texture → uri-list → text
- Works on KDE Wayland where `get_formats().contain_mime_type()` returns false
- Forwards events to server via existing IPC

**Why added:** Replaces GNOME extension's clipboard monitoring. Works on any DE with GTK4/Wayland support.

### XDG Portal Shortcut Listener

**File:** `ui/services/shortcut_listener.py` (500 lines)

**What it does:**
- Uses XDG Desktop Portal `GlobalShortcuts` API (`org.freedesktop.portal.GlobalShortcuts`)
- Creates portal session, binds shortcuts, listens for `Activated` signal
- Passes activation tokens to D-Bus service for proper Wayland focus
- Falls back gracefully when portal unavailable

**Supported DEs:**
- KDE Plasma 6+
- GNOME 48+
- Hyprland (with xdg-desktop-portal-hyprland)
- Any DE implementing the XDG GlobalShortcuts portal

**Why added:** Replaces extension-based shortcuts with standard XDG protocol.

### JSON Settings Store

**File:** `ui/infrastructure/json_settings_store.py` (88 lines)

**What it does:**
- Stores shortcuts in `~/.config/tfcbm/settings.json`
- Simple file I/O, no D-Bus dependency
- Works on any desktop environment

**Why added:** Replaces GSettings-based storage that required extension D-Bus service.

---

## Modified Components

### D-Bus Service (`server/src/dbus_service.py`)

**Removed:**
- `OnClipboardChange` method (was called by extension)
- `clipboard_handler` parameter

**Added:**
- `activate_window(activation_token, timestamp)` method
- `_set_activation_token(token)` for Wayland focus
- `_request_activation_token(timestamp)` fallback

**Why:** Clipboard events now come from in-process monitor. Activation tokens from portal enable proper Wayland window focus.

### Application Class (`ui/application/clipboard_app.py`)

**Changed:**
- Base class: `Adw.Application` → `Gtk.Application`
- Removed extension startup/shutdown code
- Added `clipboard_monitor` and `shortcut_listener` attributes
- Added `_start_clipboard_monitor()`, `_stop_clipboard_monitor()`
- Added `_start_shortcut_listener()`, `_stop_shortcut_listener()`

**Startup flow change:**
- Old: Check extension → Show error if missing → Enable extension
- New: Load window → Start clipboard monitor → Start shortcut listener

### Shortcut Service (`ui/services/shortcut_service.py`)

**Removed:**
- `_check_extension_ready()` method (46 lines)
- Extension availability checks before operations

**Why:** Settings are always available via JSON store. No extension to wait for.

---

## Build System Changes

### meson.build

**Removed:**
- GNOME extension bundling: `install_subdir('gnome-extension', ...)`
- Extension installer script: `tfcbm-install-extension.sh` from `configure_file`

**Version:** `1.0` → `1.0.1`

### Manifest Source

**Changed from:**
```yaml
sources:
  - type: git
    url: https://github.com/dyslechtchitect/tfcbm.git
    tag: v1.0
    commit: 45ab950633ca6b12ac3dd316abaf4e0ba21958f7
```

**Changed to:**
```yaml
sources:
  - type: dir
    path: .
```

**Note:** For Flathub submission, this will need to reference the release tag.

---

## Summary Table

| Component | Before (Main) | After (Beta) |
|-----------|---------------|--------------|
| Clipboard monitoring | GNOME extension via D-Bus | In-process `ClipboardMonitor` (GTK4) |
| Global shortcuts | GNOME extension via GSettings | XDG Portal `GlobalShortcuts` |
| Settings storage | GSettings via extension D-Bus | JSON file (`~/.config/tfcbm/settings.json`) |
| Base application class | `Adw.Application` | `Gtk.Application` |
| Extension installation | Required, with setup dialog | Not needed |
| Supported DEs | GNOME only | GNOME, KDE, Hyprland, others |

---

## Lines of Code Impact

| Category | Removed | Added | Net |
|----------|---------|-------|-----|
| GNOME extension | 2,900+ | 0 | -2,900 |
| Extension UI/checks | 1,024 | 0 | -1,024 |
| GSettings store | 629 | 0 | -629 |
| Clipboard monitor | 0 | 271 | +271 |
| Shortcut listener | 0 | 500 | +500 |
| JSON settings | 0 | 88 | +88 |
| **Total** | **4,553+** | **859** | **-3,694** |

The new architecture is significantly simpler while supporting more desktop environments.
