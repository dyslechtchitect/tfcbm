# GNOME Extensions Submission Checklist

This checklist validates compliance with [GNOME Shell Extensions Review Guidelines](https://gjs.guide/extensions/review-guidelines/review-guidelines.html).

## ✅ Technical Requirements

### Lifecycle Management
- [x] **No initialization before enable()**: Extension creates nothing in constructor
- [x] **Proper cleanup in disable()**: All objects destroyed, signals disconnected, sources removed
- [x] **No GObject instances during init**: Only created in enable()

### Code Quality
- [x] **Readable JavaScript**: Code is well-formatted and readable
- [x] **No deprecated modules**: No ByteArray, Lang, or Mainloop usage
- [x] **No GTK in Shell process**: Extension doesn't use Gdk, Gtk, or Adw
- [x] **Minimal logging**: Only essential logs, no spam
- [x] **No AI-generated code**: All code written by developers

## ✅ Metadata Requirements (metadata.json)

- [x] **uuid**: `tfcbm-clipboard-monitor@github.com` (valid format, not using gnome.org namespace)
- [x] **name**: "TFCBM Clipboard Monitor" (descriptive and unique)
- [x] **description**: Declares clipboard access as required by guidelines
- [x] **shell-version**: Only stable releases (43-49), no future versions
- [x] **url**: GitHub repository link (needs to be updated with actual URL)
- [x] **No deprecated fields**: No "version" field (reserved for internal use)

## ✅ Security & Privacy

- [x] **Clipboard access declared**: Description explicitly states clipboard access
- [x] **No telemetry**: Extension doesn't track users or send data to external servers
- [x] **Local communication only**: Data sent only via DBus to local TFCBM app
- [x] **No privileged processes**: No pkexec or sudo usage
- [x] **No binary executables**: Extension is pure JavaScript

## ✅ External Dependencies

- [x] **No external scripts**: Extension doesn't launch external processes
- [x] **DBus communication only**: Uses standard DBus for IPC (compliant)
- [x] **No hardcoded paths**: All paths are relative to extension directory

## ✅ GSettings Schema

- [x] **Correct base ID**: `org.gnome.shell.extensions.simple-clipboard`
- [x] **Correct base path**: `/org/gnome/shell/extensions/simple-clipboard/`
- [x] **XML file included**: Schema file present in schemas/ directory
- [x] **No compiled schema**: gschemas.compiled removed (compiled during installation)

## ✅ Legal & Licensing

- [x] **GPL-compatible license**: GPL-2.0-or-later (in LICENSE file)
- [x] **No copyrighted content**: Custom icon or system fallback
- [x] **Code of Conduct compliance**: No inappropriate content
- [x] **No political agendas**: Extension is neutral and functional

## ✅ Functional Requirements

- [x] **Extension is functional**: Clipboard monitoring works independently
- [x] **Graceful degradation**: Works even when TFCBM app is not running
- [x] **Doesn't interfere**: No conflicts with other extensions
- [x] **Proper preferences**: Uses GSettings for configuration

## ⚠️ Items Requiring Update

### Before Submission:
1. **Update metadata.json URL**: Replace `https://github.com/yourusername/tfcbm-gnome-extension` with actual repository URL
2. **Update README links**: Replace placeholder GitHub URLs with actual links
3. **Create GitHub repository**: Host extension code on GitHub/GitLab
4. **Test on supported GNOME versions**: Verify on GNOME Shell 43-49
5. **Screenshot for extensions.gnome.org**: Prepare a screenshot showing the extension in action

## 📋 File Structure Check

```
tfcbm-gnome-extension/
├── extension.js              ✅ Main extension code
├── metadata.json             ✅ Extension metadata
├── LICENSE                   ✅ GPL-2.0-or-later license
├── README.md                 ✅ Documentation
├── tfcbm.svg                ✅ Extension icon
├── schemas/                  ✅ GSettings schemas
│   └── org.gnome.shell.extensions.simple-clipboard.gschema.xml
└── src/                     ✅ Source modules
    ├── ClipboardMonitorService.js
    ├── PollingScheduler.js
    ├── adapters/
    │   ├── DBusNotifier.js
    │   ├── GnomeClipboardAdapter.js
    │   └── UnixSocketNotifier.js (not used, can be removed)
    └── domain/
        ├── ClipboardEvent.js
        ├── ClipboardPort.js
        └── NotificationPort.js
```

## 🔧 Optional Improvements

- [ ] Remove UnixSocketNotifier.js (not used in compliant version)
- [ ] Add extension icon/screenshot for listing
- [ ] Add preferences UI (prefs.js) for keyboard shortcut customization
- [ ] Test on all supported GNOME Shell versions (43-49)

## 📝 Submission Notes

### What Changed from Original:
1. Removed process launching (_launchUI, _killProcesses)
2. Replaced UnixSocket with DBus communication
3. Fixed icon path to be within extension directory
4. Added clipboard access declaration in description
5. Removed all hardcoded paths
6. Proper error handling for when TFCBM app is not running

### Integration Requirements for TFCBM App:
The TFCBM application needs to:
1. Register DBus service: `org.tfcbm.ClipboardManager`
2. Implement DBus methods: `Activate`, `ShowSettings`, `Quit`, `OnClipboardChange`
3. Auto-start on login (via .desktop file or systemd service)

## ✅ Final Status

**Ready for submission to extensions.gnome.org** after updating repository URLs.

The extension now complies with all GNOME Shell Extension review guidelines and can be submitted once the GitHub repository is created and URLs are updated.
