#!/bin/bash

# TFCBM Log Viewer
# Shows all TFCBM-related logs in real-time

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${GREEN}TFCBM Log Viewer${NC}"
echo -e "${YELLOW}Showing TFCBM app logs and GNOME Shell extension logs...${NC}"
echo -e "${CYAN}Press Ctrl+C to stop${NC}"
echo ""

# Show both TFCBM Flatpak app logs and GNOME Shell extension logs
journalctl --user -f \
  -u "app-flatpak-io.github.dyslechtchitect.tfcbm*" \
  -t gnome-shell \
  --no-hostname \
  --output=short
