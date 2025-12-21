# TFCBM + GNOME Extension - Quick Start Guide

## Installation (5 Minutes)

### Step 1: Install the Extension Files
```bash
cd /home/ron/Documents/git/tfcbm-gnome-extension

# Clean install (remove old version if exists)
rm -rf ~/.local/share/gnome-shell/extensions/tfcbm-clipboard-monitor@github.com/

# Copy extension files (excluding git/ide files)
mkdir -p ~/.local/share/gnome-shell/extensions/tfcbm-clipboard-monitor@github.com/
cp extension.js metadata.json tfcbm.svg LICENSE README.md \
   ~/.local/share/gnome-shell/extensions/tfcbm-clipboard-monitor@github.com/
cp -r schemas src \
   ~/.local/share/gnome-shell/extensions/tfcbm-clipboard-monitor@github.com/
```

### Step 2: Restart GNOME Shell (Required!)

**X11:** Press `Alt+F2`, type `r`, press Enter
**Wayland:** Log out and log back in

### Step 3: Enable the Extension
```bash
gnome-extensions enable tfcbm-clipboard-monitor@github.com

# Verify it's enabled
gnome-extensions list --enabled | grep tfcbm
```

### Step 4: Set Up Auto-Start
```bash
cd /home/ron/Documents/git/TFCBM
cp org.tfcbm.ClipboardManager.desktop.autostart ~/.config/autostart/org.tfcbm.ClipboardManager.desktop
```

### Step 5: Start TFCBM Now (or restart to auto-start)
```bash
cd /home/ron/Documents/git/TFCBM
./.venv/bin/python3 launcher.py &
```

## Verify It's Working

### Check 1: DBus Service
```bash
busctl --user list | grep tfcbm
```
Expected output: `org.tfcbm.ClipboardManager`

### Check 2: Copy Some Text
Copy this text → Check server log:
```bash
tail -20 /tmp/tfcbm_server.log
```
Expected: "Processing clipboard event via DBus: text"

### Check 3: Tray Icon
Look for TFCBM icon in system tray → Click it → Window should toggle

### Check 4: Keyboard Shortcut
Press `Ctrl+Escape` → Window should toggle

## Troubleshooting

**Extension not working?**
```bash
journalctl -f -o cat /usr/bin/gnome-shell | grep -i tfcbm
```

**TFCBM not receiving events?**
```bash
tail -100 /tmp/tfcbm_server.log
```

**Start fresh:**
```bash
pkill -9 -f tfcbm
cd /home/ron/Documents/git/TFCBM
./.venv/bin/python3 launcher.py
```

## Done!

- **Extension** ✓ Monitors clipboard & manages tray icon
- **TFCBM Server** ✓ Stores clipboard data in database
- **TFCBM UI** ✓ Shows clipboard history
- **DBus** ✓ Connects everything

For more details, see:
- `GNOME_EXTENSION_INTEGRATION.md` - Full integration guide
- `DBUS_INTEGRATION_SUMMARY.md` - Technical details
