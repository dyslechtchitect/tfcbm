#!/bin/bash
# TFCBM Ubuntu Debug Script
# Run this on Ubuntu to diagnose extension issues

echo "=== TFCBM Ubuntu Debug ==="
echo ""

echo "1. GNOME Shell Version:"
gnome-shell --version
echo ""

echo "2. Session Type:"
echo "XDG_SESSION_TYPE=$XDG_SESSION_TYPE"
echo ""

echo "3. Flatpak Installed:"
flatpak list | grep tfcbm || echo "NOT INSTALLED"
echo ""

echo "4. Extension Directory:"
ls -la ~/.local/share/gnome-shell/extensions/ | grep tfcbm || echo "NOT FOUND"
echo ""

echo "5. Extension Status:"
gnome-extensions list | grep tfcbm || echo "NOT IN LIST"
echo ""

if gnome-extensions list | grep -q tfcbm; then
    echo "6. Extension Info:"
    gnome-extensions info tfcbm-clipboard-monitor@github.com
    echo ""
fi

echo "7. Try to enable extension:"
gnome-extensions enable tfcbm-clipboard-monitor@github.com 2>&1
echo ""

echo "8. Check if extension zip exists in Flatpak:"
flatpak run --command=sh io.github.dyslechtchitect.tfcbm -c "ls -la /app/share/tfcbm/ | grep zip" || echo "NOT FOUND IN FLATPAK"
echo ""

echo "9. TFCBM App Logs (last 50 lines):"
journalctl --user -b | grep -i tfcbm | tail -50
echo ""

echo "=== Instructions ==="
echo ""
echo "If extension shows 'State: DISABLED':"
echo "  1. Run: gnome-extensions enable tfcbm-clipboard-monitor@github.com"
echo "  2. Log out and log back in (required on Wayland)"
echo "  3. Launch TFCBM again"
echo ""
echo "If extension not installed at all:"
echo "  1. Launch TFCBM app - it should show install dialog"
echo "  2. Click 'Install Extension'"
echo "  3. Log out and log back in"
echo "  4. Launch TFCBM again"
echo ""
echo "If install dialog doesn't appear:"
echo "  1. Run: flatpak run io.github.dyslechtchitect.tfcbm 2>&1 | grep -i extension"
echo "  2. Look for error messages"
echo ""
