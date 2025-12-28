# TFCBM GNOME Extension - Preparation Summary

This document summarizes the preparation work done to make the TFCBM GNOME extension ready for submission to extensions.gnome.org.

## What Was Done

### ✅ 1. Copied Extension Files
- Copied all extension files from `/TFCBM/gnome-extension/` to this repository
- Copied the extension icon (`tfcbm.svg`) into the extension directory
- Removed development files (node_modules, tests, package.json)

### ✅ 2. Removed GNOME Policy Violations

**Removed:**
- ❌ External process launching (`_launchUI()`, `GLib.spawn_command_line_async`)
- ❌ Process killing (`_killProcesses()`, `pkill` commands)
- ❌ Hardcoded paths (`/home/ron/Documents/git/TFCBM`)
- ❌ External file references (icon path pointing outside extension)

**Replaced with:**
- ✅ DBus-only communication (compliant IPC mechanism)
- ✅ Graceful handling when TFCBM app is not running
- ✅ Icon path relative to extension directory
- ✅ Clean separation of concerns

### ✅ 3. Fixed metadata.json

**Changes:**
- UUID: `simple-clipboard@tfcbm` → `tfcbm-clipboard-monitor@github.com`
- Name: More descriptive "TFCBM Clipboard Monitor"
- Description: Added mandatory clipboard access declaration
- Removed: `keybindings` field (moved to GSettings only)
- Removed: `version` field (reserved for internal use)
- Shell versions: Limited to stable releases (43-49)

### ✅ 4. Created DBus-Based Communication

**New file:** `src/adapters/DBusNotifier.js`
- Sends clipboard events via DBus instead of Unix sockets
- Implements backoff to prevent spamming when app is not running
- Graceful error handling

**Updated:** `extension.js`
- Removed all process management code
- Uses only DBus for communication
- Added `_quitApp()` method (sends Quit via DBus instead of pkill)
- Simplified error handling

### ✅ 5. Added Documentation

**Created files:**
- `README.md` - Installation, usage, and integration instructions
- `LICENSE` - GPL-2.0-or-later license (GNOME-compatible)
- `SUBMISSION_CHECKLIST.md` - Validation against GNOME requirements
- `TFCBM_INTEGRATION_GUIDE.md` - Guide for integrating TFCBM app with extension
- `PREPARATION_SUMMARY.md` - This file

### ✅ 6. Validated Compliance

All GNOME Shell Extension guidelines requirements met:
- ✅ No objects created before enable()
- ✅ Proper cleanup in disable()
- ✅ Readable, non-obfuscated JavaScript
- ✅ No deprecated modules
- ✅ No external executables
- ✅ No telemetry
- ✅ Clipboard access declared
- ✅ GPL-compatible license
- ✅ Correct GSettings schema

## Current Status

### ✅ Ready for Submission
The extension is **technically ready** for submission to extensions.gnome.org.

### ⚠️ Before Submission

**Required:**
1. Create GitHub repository for this extension
2. Update `metadata.json` URL field with actual repository URL
3. Update `README.md` placeholder URLs
4. Test on GNOME Shell 43-49
5. Prepare screenshot for extensions.gnome.org listing

**Optional:**
6. Add prefs.js for preferences UI
7. Create extension icon/logo for listing page
8. Add more comprehensive documentation

## Architecture Changes

### Old (Non-Compliant):
```
Extension → Launches TFCBM Python app
          → Kills TFCBM processes
          → Uses Unix socket for communication
          → Hardcoded paths
```

### New (Compliant):
```
Extension → Monitors clipboard
          → Manages tray icon & shortcuts
          → Sends data via DBus

TFCBM App → Started independently (autostart)
          → Registers DBus service
          → Receives clipboard events
          → Controlled via DBus
```

## Next Steps

### For Extension (this repo):
1. Create GitHub repository
2. Update URLs in metadata.json and README.md
3. Test on all supported GNOME versions
4. Submit to extensions.gnome.org
5. (Optional) Add preferences UI

### For TFCBM Application (main repo):
1. Implement DBus service registration
2. Add DBus methods: `Activate`, `ShowSettings`, `Quit`, `OnClipboardChange`
3. Create autostart .desktop file or systemd service
4. Remove Unix socket code (replaced by DBus)
5. Update documentation

See `TFCBM_INTEGRATION_GUIDE.md` for detailed implementation instructions.

## File Structure

```
tfcbm-gnome-extension/
├── extension.js                      # Main extension (no process launching)
├── metadata.json                     # Fixed metadata (clipboard declaration)
├── tfcbm.svg                        # Icon (inside extension directory)
├── LICENSE                           # GPL-2.0-or-later
├── README.md                         # User documentation
├── SUBMISSION_CHECKLIST.md          # Compliance validation
├── TFCBM_INTEGRATION_GUIDE.md       # Integration guide for TFCBM app
├── PREPARATION_SUMMARY.md           # This file
├── schemas/
│   └── org.gnome.shell.extensions.simple-clipboard.gschema.xml
└── src/
    ├── ClipboardMonitorService.js
    ├── PollingScheduler.js
    ├── adapters/
    │   ├── DBusNotifier.js          # NEW: DBus communication
    │   └── GnomeClipboardAdapter.js
    └── domain/
        ├── ClipboardEvent.js
        ├── ClipboardPort.js
        └── NotificationPort.js
```

## Benefits of New Architecture

### For Users:
- ✅ Can install extension from extensions.gnome.org (official source)
- ✅ Can install TFCBM app from Flatpak/package manager
- ✅ Extension and app can be updated independently
- ✅ More reliable communication (DBus is standard)

### For Developers:
- ✅ Cleaner separation of concerns
- ✅ Easier to maintain and debug
- ✅ Follows GNOME best practices
- ✅ No policy violations
- ✅ Can be distributed through official channels

### For Distribution:
- ✅ Extension: extensions.gnome.org
- ✅ App: Flatpak, Flathub, distro repos
- ✅ Both can have independent release cycles
- ✅ Wider reach and easier installation

## Testing Checklist

Before submission, test:
- [ ] Extension loads without errors on GNOME 43
- [ ] Extension loads without errors on GNOME 44
- [ ] Extension loads without errors on GNOME 45
- [ ] Extension loads without errors on GNOME 46
- [ ] Extension loads without errors on GNOME 47
- [ ] Extension loads without errors on GNOME 48
- [ ] Extension loads without errors on GNOME 49
- [ ] Clipboard monitoring works
- [ ] Keyboard shortcut works
- [ ] Tray icon appears
- [ ] Clicking tray icon activates TFCBM (when running)
- [ ] Extension gracefully handles TFCBM not running
- [ ] Extension can be enabled/disabled without errors
- [ ] No error spam in journalctl logs
- [ ] Extension disable() properly cleans up all resources

## Submission Process

1. **Create account** on extensions.gnome.org
2. **Upload extension** as .zip file:
   ```bash
   cd /home/ron/Documents/git/tfcbm-gnome-extension
   zip -r tfcbm-extension.zip . -x ".git/*" ".claude/*"
   ```
3. **Fill in details:**
   - Name: TFCBM Clipboard Monitor
   - Description: (from metadata.json)
   - Screenshot: (prepare one showing the extension in action)
   - License: GPL-2.0-or-later
4. **Submit for review**
5. **Wait for approval** (GNOME reviewers will check compliance)

## Support

If you encounter issues during submission:
- Review `SUBMISSION_CHECKLIST.md`
- Check GNOME review guidelines: https://gjs.guide/extensions/review-guidelines/
- Ask in GNOME Matrix channel: #extensions:gnome.org

---

**Prepared:** 2025-12-21
**Status:** ✅ Ready for submission (pending URL updates)
**Compliance:** ✅ All GNOME guidelines met
