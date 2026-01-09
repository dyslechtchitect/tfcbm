# Ubuntu Extension Debugging Guide

## Problem
GNOME extension doesn't load/enable on Ubuntu, so tray icon doesn't appear.

## Root Causes Fixed

### 1. GNOME Shell Version Mismatch ✅ FIXED
**Problem:** Extension only supported GNOME Shell 49 (Fedora)
- Ubuntu 24.04: GNOME Shell 46
- Ubuntu 24.10: GNOME Shell 47

**Fix:** Updated `gnome-extension/metadata.json` to support versions 45-49

### 2. Unreliable Extension Auto-Enable ✅ FIXED
**Problem:** DBus EnableExtension method doesn't work reliably across all distros
**Fix:** Added fallback to `gnome-extensions enable` command in `main.py`

## Debugging on Ubuntu

### Step 1: Check if extension is installed
```bash
flatpak run --command=sh io.github.dyslechtchitect.tfcbm
ls ~/.local/share/gnome-shell/extensions/
```
Look for: `tfcbm-clipboard-monitor@github.com`

### Step 2: Check GNOME Shell version
```bash
gnome-shell --version
```
Should see: 45, 46, 47, 48, or 49

### Step 3: List extensions
```bash
gnome-extensions list
```
Should include: `tfcbm-clipboard-monitor@github.com`

### Step 4: Check extension info
```bash
gnome-extensions info tfcbm-clipboard-monitor@github.com
```
Look for:
- `State: ENABLED` or `State: ACTIVE` (good)
- `State: DISABLED` (needs enabling)
- Shell version compatibility

### Step 5: Manual install (if not installed)
```bash
flatpak run --command=tfcbm-install-extension io.github.dyslechtchitect.tfcbm
```

### Step 6: Manual enable (if installed but disabled)
```bash
gnome-extensions enable tfcbm-clipboard-monitor@github.com
```

### Step 7: Restart GNOME Shell
**On X11:**
- Press Alt+F2
- Type `r`
- Press Enter

**On Wayland:**
- Log out and log back in

### Step 8: Check logs
```bash
# Check flatpak logs
flatpak run --command=sh io.github.dyslechtchitect.tfcbm -c "python3 /app/lib/tfcbm/main.py 2>&1 | grep -i extension"

# Check GNOME Shell logs
journalctl -f -o cat /usr/bin/gnome-shell | grep tfcbm
```

## Common Issues

### Issue: "Extension is not compatible with current GNOME version"
**Solution:** Extension now supports 45-49, but you need to rebuild the flatpak with updated metadata.json

### Issue: Extension installs but doesn't enable
**Solution:**
1. Manually enable: `gnome-extensions enable tfcbm-clipboard-monitor@github.com`
2. Restart GNOME Shell (see Step 7)

### Issue: Extension enables but tray icon doesn't appear
**Check:**
1. Is autostart enabled? Extension only shows when autostart is on
2. Is the app actually running? Check with `ps aux | grep tfcbm`
3. Check GNOME Shell logs for JavaScript errors

### Issue: flatpak-spawn command not found
**Solution:** Ensure Flatpak has permission to spawn host commands:
```bash
flatpak override --user io.github.dyslechtchitect.tfcbm --talk-name=org.freedesktop.Flatpak
```

## What's Required for Extension to Work

1. ✅ Extension installed in `~/.local/share/gnome-shell/extensions/`
2. ✅ Extension enabled via `gnome-extensions enable`
3. ✅ GNOME Shell restarted (X11) or session restarted (Wayland)
4. ✅ TFCBM app running
5. ✅ Autostart enabled in app settings

## Changes Made for Ubuntu Compatibility

1. **gnome-extension/metadata.json:** Added shell-version 45-49
2. **main.py:** Added fallback extension enable method using gnome-extensions command
3. **Improved logging:** Better error messages for debugging

## Testing Commands

```bash
# Reinstall flatpak with new changes
flatpak-builder --user --install --force-clean build-dir io.github.dyslechtchitect.tfcbm.yml

# Run app and watch logs
flatpak run io.github.dyslechtchitect.tfcbm 2>&1 | grep -i extension

# Check extension status
gnome-extensions info tfcbm-clipboard-monitor@github.com

# Enable if needed
gnome-extensions enable tfcbm-clipboard-monitor@github.com
```
