#!/bin/bash

# TFCBM Packaging Validation Script
# Checks if all required files are ready for submission

set -e

echo "═══════════════════════════════════════════════════════════"
echo "  TFCBM Packaging Validation"
echo "═══════════════════════════════════════════════════════════"
echo ""

ERRORS=0
WARNINGS=0

# Color codes
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

check_file() {
    if [ -f "$1" ]; then
        echo -e "${GREEN}✓${NC} Found: $1"
    else
        echo -e "${RED}✗${NC} Missing: $1"
        ((ERRORS++))
    fi
}

check_placeholder() {
    if grep -q "$2" "$1" 2>/dev/null; then
        echo -e "${RED}✗${NC} Placeholder URL found in $1: $2"
        ((ERRORS++))
    else
        echo -e "${GREEN}✓${NC} No placeholder URLs in $1"
    fi
}

echo "1. Checking required files..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
check_file "org.tfcbm.ClipboardManager.yml"
check_file "org.tfcbm.ClipboardManager.metainfo.xml"
check_file "org.tfcbm.ClipboardManager.desktop"
check_file "tfcbm-gnome-extension.zip"
check_file "LICENSE"
echo ""

echo "2. Checking icon files..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
for size in 16x16 32x32 48x48 64x64 128x128 256x256 512x512; do
    check_file "icons/hicolor/${size}/apps/org.tfcbm.ClipboardManager.png"
done
check_file "icons/hicolor/scalable/apps/org.tfcbm.ClipboardManager.svg"
echo ""

echo "3. Checking for placeholder URLs..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
check_placeholder "org.tfcbm.ClipboardManager.metainfo.xml" "yourusername"
check_placeholder "gnome-extension/metadata.json" "yourusername"
echo ""

echo "4. Checking screenshots directory..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ -d "screenshots" ]; then
    screenshot_count=$(find screenshots -name "*.png" 2>/dev/null | wc -l)
    if [ "$screenshot_count" -gt 0 ]; then
        echo -e "${GREEN}✓${NC} Found $screenshot_count screenshot(s)"
        find screenshots -name "*.png" -exec basename {} \; | sed 's/^/  - /'
    else
        echo -e "${YELLOW}⚠${NC} Screenshots directory exists but is empty"
        ((WARNINGS++))
    fi
else
    echo -e "${YELLOW}⚠${NC} No screenshots directory found"
    echo "  Create with: mkdir screenshots"
    ((WARNINGS++))
fi
echo ""

echo "5. Validating metadata (if tools are installed)..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if command -v appstream-util &> /dev/null; then
    if appstream-util validate-relax org.tfcbm.ClipboardManager.metainfo.xml 2>&1; then
        echo -e "${GREEN}✓${NC} AppData validation passed"
    else
        echo -e "${RED}✗${NC} AppData validation failed"
        ((ERRORS++))
    fi
else
    echo -e "${YELLOW}⚠${NC} appstream-util not found (install: sudo dnf install libappstream-glib)"
    ((WARNINGS++))
fi
echo ""

if command -v desktop-file-validate &> /dev/null; then
    if desktop-file-validate org.tfcbm.ClipboardManager.desktop 2>&1; then
        echo -e "${GREEN}✓${NC} Desktop file validation passed"
    else
        echo -e "${RED}✗${NC} Desktop file validation failed"
        ((ERRORS++))
    fi
else
    echo -e "${YELLOW}⚠${NC} desktop-file-validate not found (install: sudo dnf install desktop-file-utils)"
    ((WARNINGS++))
fi
echo ""

echo "6. Checking extension package..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ -f "tfcbm-gnome-extension.zip" ]; then
    size=$(ls -lh tfcbm-gnome-extension.zip | awk '{print $5}')
    echo -e "${GREEN}✓${NC} Extension package: $size"

    # Check contents
    if command -v unzip &> /dev/null; then
        echo "  Contents:"
        unzip -l tfcbm-gnome-extension.zip | grep -E "(extension.js|metadata.json|schemas/)" | awk '{print "  - " $4}'
    fi
fi
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  VALIDATION SUMMARY"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}✓ ALL CHECKS PASSED!${NC}"
    echo ""
    echo "Your project is ready for submission!"
    echo "Next steps:"
    echo "  1. Read TODO_BEFORE_SUBMISSION.txt"
    echo "  2. Follow FLATPAK_SUBMISSION_GUIDE.md"
    exit 0
elif [ $ERRORS -eq 0 ]; then
    echo -e "${YELLOW}⚠ $WARNINGS WARNING(S)${NC}"
    echo ""
    echo "You can proceed but should address the warnings."
    echo "See TODO_BEFORE_SUBMISSION.txt for required updates."
    exit 0
else
    echo -e "${RED}✗ $ERRORS ERROR(S)${NC}"
    if [ $WARNINGS -gt 0 ]; then
        echo -e "${YELLOW}⚠ $WARNINGS WARNING(S)${NC}"
    fi
    echo ""
    echo "Please fix the errors before submitting."
    echo "See TODO_BEFORE_SUBMISSION.txt for required updates."
    exit 1
fi
