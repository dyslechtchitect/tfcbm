#!/bin/bash

# Quick integration test for TFCBM features

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== TFCBM Integration Test ==="
echo ""

# Test 1: Python infrastructure
echo "[1/5] Testing Python keyboard shortcut infrastructure..."
source .venv/bin/activate
python3 -c "
from ui.domain.keyboard import KeyboardShortcut
from ui.infrastructure.gsettings_store import GSettingsStore
from ui.infrastructure.gtk_keyboard_parser import GtkKeyboardParser
from ui.services.shortcut_service import ShortcutService

# Test shortcut creation and parsing
shortcut = KeyboardShortcut(modifiers=['Ctrl', 'Alt'], key='t')
assert shortcut.to_display_string() == 'Ctrl+Alt+t'
assert '<Ctrl><Alt>t' in shortcut.to_gtk_string()

# Test parsing
parsed = KeyboardShortcut.from_gtk_string('<Control><Shift>k')
assert parsed.to_display_string() == 'Ctrl+Shift+k'

print('✓ Python infrastructure OK')
"

# Test 2: Check extension syntax
echo "[2/5] Checking GNOME extension syntax..."
node --check gnome-extension/extension.js
echo "✓ Extension syntax OK"

# Test 3: Check schemas
echo "[3/5] Checking GSettings schemas..."
if [ -f "gnome-extension/schemas/gschemas.compiled" ]; then
    echo "✓ Schemas compiled"
else
    echo "✗ Schemas not compiled (run: glib-compile-schemas gnome-extension/schemas/)"
    exit 1
fi

# Test 4: Check run.sh
echo "[4/5] Checking run.sh script..."
if [ -x "run.sh" ]; then
    echo "✓ run.sh is executable"
else
    echo "✗ run.sh is not executable"
    exit 1
fi

# Test 5: Check resources
echo "[5/5] Checking resources..."
if [ -f "resouces/tfcbm.svg" ]; then
    echo "✓ Tray icon exists"
else
    echo "⚠ Tray icon not found (will use fallback)"
fi

echo ""
echo "=== All Tests Passed! ==="
echo ""
echo "To launch TFCBM, run: ./run.sh"
echo ""
