#!/bin/bash
set -x

echo "=== TFCBM Complete Cleanup ==="
echo ""

# 1. Kill any running TFCBM processes
echo "Killing TFCBM processes..."
killall -9 python3 2>/dev/null || true
flatpak kill org.tfcbm.ClipboardManager 2>/dev/null || true

# 2. Uninstall Flatpak
echo "Uninstalling Flatpak..."
flatpak uninstall --user org.tfcbm.ClipboardManager -y 2>/dev/null || true

# 3. Remove GNOME extension
echo "Removing GNOME extension..."
gnome-extensions uninstall tfcbm-clipboard-monitor@github.com 2>/dev/null || true
rm -rf ~/.local/share/gnome-shell/extensions/tfcbm-clipboard-monitor@github.com

# 4. Remove Flatpak data directory
echo "Removing Flatpak data..."
rm -rf ~/.var/app/org.tfcbm.ClipboardManager

# 5. Remove cache files
echo "Removing cache files..."
rm -rf ~/.cache/tfcbm*
rm -f ~/.cache/tfcbm-clipboard-monitor@github.com.zip

# 6. Remove autostart file
echo "Removing autostart..."
rm -f ~/.config/autostart/org.tfcbm.ClipboardManager.desktop

# 7. Remove any desktop files
echo "Removing desktop files..."
rm -f ~/.local/share/applications/org.tfcbm.ClipboardManager.desktop

# 8. Remove D-Bus service files
echo "Removing D-Bus services..."
rm -f ~/.local/share/dbus-1/services/org.tfcbm.ClipboardManager.service

# 9. Remove any settings
echo "Removing settings..."
gsettings reset-recursively org.tfcbm.ClipboardManager 2>/dev/null || true

# 10. Clean Flatpak repo if it exists
echo "Cleaning Flatpak build artifacts..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
rm -rf "$SCRIPT_DIR/repo"
rm -rf "$SCRIPT_DIR/.flatpak-builder"

echo ""
echo "=== Cleanup Complete ==="
echo ""
echo "To verify everything is removed:"
echo "  flatpak list | grep tfcbm          # Should show nothing"
echo "  gnome-extensions list | grep tfcbm  # Should show nothing"
echo "  ls ~/.var/app/ | grep tfcbm        # Should show nothing"
echo ""
echo "To do a fresh install:"
echo "  cd $SCRIPT_DIR"
echo "  git pull"
echo "  flatpak-builder --force-clean --user --install repo org.tfcbm.ClipboardManager.yml"
echo "  flatpak run org.tfcbm.ClipboardManager"
echo ""
