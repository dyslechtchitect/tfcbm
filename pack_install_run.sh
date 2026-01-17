#!/bin/bash
set -e

# TFCBM Pack, Install, and Run Script
# Rebuilds the Flatpak, installs it, and runs it

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}TFCBM Pack, Install, and Run${NC}"
echo ""

# Step 1: Build and install
echo -e "${YELLOW}Step 1/1: Building and installing Flatpak...${NC}"
flatpak-builder --user --install --force-clean --disable-rofiles-fuse build-dir io.github.dyslechtchitect.tfcbm.yml

echo ""
echo -e "${GREEN}Flatpak built and installed. You can now run it using: ${NC}"
echo -e "${YELLOW}flatpak run io.github.dyslechtchitect.tfcbm${NC}"
