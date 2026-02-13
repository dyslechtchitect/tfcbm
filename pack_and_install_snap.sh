#!/bin/bash
set -e

# TFCBM Pack and Install Snap Script
# Builds the snap and installs it locally

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}TFCBM Snap Pack and Install${NC}"
echo ""

# Step 1: Build snap
echo -e "${YELLOW}Step 1/2: Pulling snap source...${NC}"
snapcraft pull tfcbm

echo -e "${YELLOW}Step 1.1/2: Building snap...${NC}"
snapcraft pack

# Find the built snap file
SNAP_FILE=$(ls -t tfcbm_*.snap 2>/dev/null | head -1)
if [ -z "$SNAP_FILE" ]; then
    echo -e "${RED}Error: No .snap file found after build${NC}"
    exit 1
fi

# Step 1.5: Inspect snap contents for debugging
echo -e "${YELLOW}Step 1.5/2: Inspecting ${SNAP_FILE} contents...${NC}"
UNPACK_DIR="squashfs-root"
if [ -d "$UNPACK_DIR" ]; then
    sudo rm -rf "$UNPACK_DIR"
fi
unsquashfs "$SNAP_FILE"
echo -e "${YELLOW}Contents of ${UNPACK_DIR}/usr/lib/tfcbm/ui/:${NC}"
ls -l "${UNPACK_DIR}/usr/lib/tfcbm/ui/" || echo -e "${RED}Error: Directory ${UNPACK_DIR}/usr/lib/tfcbm/ui/ not found.${NC}"
echo -e "${YELLOW}Contents of ${UNPACK_DIR}/usr/lib/tfcbm/:${NC}"
ls -l "${UNPACK_DIR}/usr/lib/tfcbm/" || echo -e "${RED}Error: Directory ${UNPACK_DIR}/usr/lib/tfcbm/ not found.${NC}"
echo ""

# Step 2: Install snap
echo -e "${YELLOW}Step 2/2: Installing ${SNAP_FILE}...${NC}"
sudo snap install "$SNAP_FILE" --dangerous

# Clean up unpacked snap directory
if [ -d "$UNPACK_DIR" ]; then
    sudo rm -rf "$UNPACK_DIR"
fi

echo ""
echo -e "${GREEN}Snap built and installed. You can now run it using: ${NC}"
echo -e "${YELLOW}snap run tfcbm${NC}"
