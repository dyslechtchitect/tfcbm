# "Start on Login" Toggle - Fixed Implementation

## The Problem

The original implementation was **incorrect** and violated GNOME HIG guidelines:

```python
# ❌ WRONG - This is what it was doing
def _on_autostart_toggled(self, switch_row, _param):
    if is_enabled:
        self._enable_autostart()
        self._enable_extension()  # ❌ Affects current session!
    else:
        self._disable_autostart()
        self._disable_extension()  # ❌ Affects current session!
```

**Problems:**
1. **Violated GNOME HIG**: A "Start on login" toggle should NEVER affect the current session
2. **Used DBus calls**: Called `org.gnome.Shell.Extensions.EnableExtension` immediately
3. **Confused users**: Extension appeared/disappeared instantly, not on next login
4. **Didn't sync with GNOME Settings**: If user disabled in Settings, app didn't reflect it correctly

---

## The Solution

The corrected implementation follows **XDG Desktop Entry Specification** and **GNOME conventions**:

### ✅ Correct Approach

```python
# ✅ CORRECT - Only manages autostart, doesn't touch current session
def _on_autostart_toggled(self, switch_row, _param):
    """Handle autostart toggle - only affects next login, not current session."""
    is_enabled = switch_row.get_active()

    if is_enabled:
        self._enable_autostart()
        self.on_notification("TFCBM will start automatically on next login")
    else:
        self._disable_autostart()
        self.on_notification("TFCBM will not start automatically on next login")
```

### Key Changes

#### 1. **Removed All Extension Enable/Disable Code**
- ❌ Deleted `_enable_extension()` method
- ❌ Deleted `_disable_extension()` method
- ❌ Removed all DBus calls to GNOME Shell
- ✅ Toggle now ONLY manages the autostart file

#### 2. **Proper Autostart Enable** (`~/.config/autostart/io.github.dyslechtchitect.tfcbm.desktop`)

```ini
[Desktop Entry]
Type=Application
Name=TFCBM
Comment=The F* Clipboard Manager
Exec=flatpak run io.github.dyslechtchitect.tfcbm
Icon=io.github.dyslechtchitect.tfcbm
Terminal=false
Categories=Utility;GTK;
StartupNotify=false
X-GNOME-Autostart-enabled=true
```

#### 3. **Proper Autostart Disable**

Instead of deleting the file, we set **two flags** for maximum compatibility:

```ini
[Desktop Entry]
Hidden=true                          # XDG standard
X-GNOME-Autostart-enabled=false      # GNOME-specific
# ...rest of content...
```

This approach:
- ✅ Works with GNOME Settings "Startup Applications"
- ✅ Follows XDG Desktop Entry Specification 1.5
- ✅ Allows GNOME Settings to re-enable autostart
- ✅ Persists user preference even if file is modified externally

#### 4. **Correct State Detection**

```python
def _is_autostart_enabled(self) -> bool:
    """Check if autostart is enabled by reading the XDG autostart desktop file."""
    # Checks file exists AND is not hidden/disabled

def _is_desktop_entry_enabled(self, desktop_file: Path) -> bool:
    """Check if a desktop entry is enabled (not hidden or disabled)."""
    content = desktop_file.read_text()

    # XDG standard check
    if "Hidden=true" in content:
        return False

    # GNOME-specific check
    if "X-GNOME-Autostart-enabled=false" in content:
        return False

    return True
```

This correctly reflects changes made by GNOME Settings!

---

## How It Works Now

### User Enables "Start on Login"
1. Toggle switched ON
2. Creates `~/.config/autostart/io.github.dyslechtchitect.tfcbm.desktop`
3. Shows: **"TFCBM will start automatically on next login"**
4. Current session: **No change**
5. Next login: **TFCBM starts automatically**

### User Disables "Start on Login"
1. Toggle switched OFF
2. Modifies desktop file to add `Hidden=true` and `X-GNOME-Autostart-enabled=false`
3. Shows: **"TFCBM will not start automatically on next login"**
4. Current session: **TFCBM keeps running, extension stays enabled**
5. Next login: **TFCBM doesn't start**

### User Disables in GNOME Settings
1. User opens **Settings → Apps → Startup**
2. Disables **TFCBM**
3. GNOME sets `X-GNOME-Autostart-enabled=false` in the desktop file
4. User reopens TFCBM Settings
5. Toggle shows **OFF** (correctly reflects GNOME Settings change!)

---

## Standards Compliance

### ✅ XDG Desktop Entry Specification 1.5
- Uses `Hidden=true` to hide entries ([spec section 5.7](https://specifications.freedesktop.org/desktop-entry-spec/1.5/recognized-keys.html))
- Follows autostart directory convention (`~/.config/autostart/`)
- Proper Type, Name, Exec, Icon fields

### ✅ GNOME HIG (Human Interface Guidelines)
- "Start on login" toggles affect NEXT session, not current
- Clear user notifications about behavior
- Syncs with GNOME Settings without conflicts

### ✅ Flatpak Compatibility
- Uses `flatpak run io.github.dyslechtchitect.tfcbm` for Exec command
- Works inside Flatpak sandbox (autostart dir is accessible)
- No system-wide modifications

### ✅ Flathub Best Practices
- No DBus manipulation of system services
- User-controlled behavior only
- Respects desktop environment conventions

---

## Technical Details

### File Locations

| Purpose | Path | Access |
|---------|------|--------|
| User autostart | `~/.config/autostart/*.desktop` | ✅ Read/Write |
| System autostart | `/etc/xdg/autostart/*.desktop` | ❌ Read-only |
| App desktop file | `/app/share/applications/*.desktop` (Flatpak) | ✅ Read-only |

### Key Fields

| Field | Purpose | Example |
|-------|---------|---------|
| `Type=Application` | Entry type | Required |
| `Exec=...` | Command to run | `flatpak run io.github.dyslechtchitect.tfcbm` |
| `Hidden=true` | XDG standard disable | Set when disabling autostart |
| `X-GNOME-Autostart-enabled=false` | GNOME disable | Set for GNOME compatibility |
| `StartupNotify=false` | No startup notification | Prevents "Starting..." banner |

---

## Testing Checklist

- [x] Toggle ON → File created with correct Exec command
- [x] Toggle ON → Current session unchanged
- [x] Toggle ON → App starts on next login
- [x] Toggle OFF → File modified with Hidden=true
- [x] Toggle OFF → Current session unchanged
- [x] Toggle OFF → App doesn't start on next login
- [x] Disable in GNOME Settings → Toggle reflects change
- [x] Re-enable in GNOME Settings → Toggle reflects change
- [x] Works in Flatpak
- [x] Works in non-Flatpak install
- [x] Handles legacy `tfcbm.desktop` filename

---

## References

- [XDG Desktop Entry Specification](https://specifications.freedesktop.org/desktop-entry-spec/1.5/)
- [GNOME HIG - Preferences](https://developer.gnome.org/hig/patterns/containers/preferences.html)
- [Flatpak Documentation - Autostart](https://docs.flatpak.org/en/latest/conventions.html)
- [FreeDesktop Autostart Spec](https://specifications.freedesktop.org/autostart-spec/0.5/)

---

## Migration Note

If users have the old implementation, the extension might still be enabled in their current session even if they disabled autostart. This is expected and will be cleaned up on next logout.

**No action needed** - the fix is forward-compatible and handles both old and new desktop file formats.
