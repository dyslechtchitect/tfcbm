#!/bin/bash
# Diagnostic script for TFCBM keyboard shortcut issues

echo "=========================================="
echo "TFCBM Keyboard Shortcut Diagnostics"
echo "=========================================="
echo ""

# 1. Check if TFCBM UI is running
echo "[1] Checking if TFCBM is running..."
if pgrep -f "ui/main.py" > /dev/null; then
    echo "    ✓ TFCBM UI is running (PID: $(pgrep -f 'ui/main.py'))"
else
    echo "    ✗ TFCBM UI is NOT running"
    echo "    → Run ./load.sh to start TFCBM"
fi
echo ""

# 2. Check if D-Bus service is registered
echo "[2] Checking if D-Bus service is registered..."
if gdbus introspect --session --dest org.tfcbm.ClipboardManager --object-path /org/tfcbm/ClipboardManager > /dev/null 2>&1; then
    echo "    ✓ D-Bus service 'org.tfcbm.ClipboardManager' is registered"
else
    echo "    ✗ D-Bus service is NOT registered"
    echo "    → The TFCBM UI must be running for D-Bus activation to work"
fi
echo ""

# 3. Check if keyboard shortcut is configured
echo "[3] Checking GNOME keyboard shortcuts..."
SHORTCUTS=$(gsettings get org.gnome.settings-daemon.plugins.media-keys custom-keybindings)
echo "    Custom keybindings: $SHORTCUTS"

# Look for TFCBM in the shortcuts
FOUND=false
for i in {0..99}; do
    SLOT="custom$i"
    NAME=$(gsettings get org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/$SLOT/ name 2>/dev/null)

    if [[ "$NAME" == *"TFCBM"* ]]; then
        FOUND=true
        BINDING=$(gsettings get org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/$SLOT/ binding)
        COMMAND=$(gsettings get org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/$SLOT/ command)

        echo ""
        echo "    ✓ Found TFCBM shortcut in slot: $SLOT"
        echo "      Name: $NAME"
        echo "      Key: $BINDING"
        echo "      Command: $COMMAND"
        break
    fi
done

if [ "$FOUND" = false ]; then
    echo "    ✗ No TFCBM keyboard shortcut configured"
    echo "    → Run ./setup_keyboard_shortcut.sh to set it up"
fi
echo ""

# 4. Check if activation script exists and is executable
echo "[4] Checking activation script..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ACTIVATE_SCRIPT="$SCRIPT_DIR/tfcbm-activate.sh"

if [ -f "$ACTIVATE_SCRIPT" ]; then
    echo "    ✓ Activation script exists: $ACTIVATE_SCRIPT"
    if [ -x "$ACTIVATE_SCRIPT" ]; then
        echo "    ✓ Script is executable"
    else
        echo "    ✗ Script is NOT executable"
        echo "    → Run: chmod +x $ACTIVATE_SCRIPT"
    fi
else
    echo "    ✗ Activation script NOT found at: $ACTIVATE_SCRIPT"
fi
echo ""

# 5. Test manual activation
echo "[5] Testing manual D-Bus activation..."
if gdbus call --session \
    --dest org.tfcbm.ClipboardManager \
    --object-path /org/tfcbm/ClipboardManager \
    --method org.gtk.Actions.Activate \
    "show-window" "[]" "{}" > /dev/null 2>&1; then
    echo "    ✓ Manual activation SUCCESSFUL"
    echo "    → The window should have appeared"
else
    echo "    ✗ Manual activation FAILED"
    echo "    → Make sure TFCBM is running first"
fi
echo ""

echo "=========================================="
echo "Summary & Next Steps"
echo "=========================================="
echo ""

if [ "$FOUND" = false ]; then
    echo "⚠ ISSUE: Keyboard shortcut not configured"
    echo "   FIX: Run ./setup_keyboard_shortcut.sh"
    echo ""
fi

if ! pgrep -f "ui/main.py" > /dev/null; then
    echo "⚠ ISSUE: TFCBM is not running"
    echo "   FIX: Run ./load.sh to start TFCBM"
    echo ""
fi

echo "If everything looks good but the shortcut still doesn't work:"
echo "  1. Try logging out and back in (to reload GNOME settings)"
echo "  2. Try a different key combination if there's a conflict"
echo "  3. Check VM keyboard input settings (if running in a VM)"
echo ""
