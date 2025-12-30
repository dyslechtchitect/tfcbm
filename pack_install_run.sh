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
echo -e "${YELLOW}Step 1/2: Building and installing Flatpak...${NC}"
flatpak-builder --user --install --force-clean build-dir io.github.dyslechtchitect.tfcbm.yml

# Step 2: Run
echo ""
echo -e "${YELLOW}Step 2/2: Running TFCBM...${NC}"
echo -e "${GREEN}Starting application...${NC}"
echo ""
flatpak run io.github.dyslechtchitect.tfcbm
