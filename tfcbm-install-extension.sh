#!/bin/bash
set -e

EXTENSION_UUID="tfcbm-clipboard-monitor@github.com"

# If running inside Flatpak, this script should do nothing related to installation
if [ -n "${FLATPAK_ID}" ]; then
    echo "This script is for native extension installation and should not be run from within Flatpak."
    echo "For Flatpak users, the TFCBM application will provide instructions for extension management."
    exit 0
fi

# Running on host (non-Flatpak)
echo "Running native GNOME extension installer..."
# Execute the install.sh script located in the gnome-extension subdirectory
# We need to change to that directory first for relative paths in install.sh to work
(cd gnome-extension && ./install.sh)
exit 0 # Exit after running native installer

