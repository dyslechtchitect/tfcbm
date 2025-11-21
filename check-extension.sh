#!/bin/bash
echo "=== Checking TFCBM Extension Status ==="
echo ""
echo "1. Extension installed:"
ls -la ~/.local/share/gnome-shell/extensions/simple-clipboard@tfcbm/extension.js 2>&1 | head -1
echo ""
echo "2. Extension enabled in settings:"
gsettings get org.gnome.shell enabled-extensions | grep -o "simple-clipboard@tfcbm" || echo "NOT ENABLED"
echo ""
echo "3. Extension loaded in GNOME Shell (check logs):"
journalctl --user -b | grep "\[TFCBM\] Keybinding" | tail -2
echo ""
echo "If you see '[TFCBM] Keybinding added successfully', Ctrl+Esc should work!"
