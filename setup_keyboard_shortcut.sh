#!/bin/bash
# Setup GNOME keyboard shortcut for TFCBM activation

# Get the absolute path to activation script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ACTIVATE_SCRIPT="$SCRIPT_DIR/tfcbm-activate.sh"

# Command to run - use DBus to activate the window
COMMAND="$ACTIVATE_SCRIPT"

# Create a custom keyboard shortcut in GNOME
# Find an available slot (custom0 to custom99)
for i in {0..99}; do
    SLOT="custom$i"

    # Check if this slot is empty
    NAME=$(gsettings get org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/$SLOT/ name 2>/dev/null)

    if [ -z "$NAME" ] || [ "$NAME" = "''" ]; then
        echo "Found available slot: $SLOT"

        # Set the keyboard shortcut
        gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/$SLOT/ name 'TFCBM Activate'
        gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/$SLOT/ command "$COMMAND"
        gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/$SLOT/ binding '<Control>Escape'

        # Get current list of custom keybindings
        CURRENT=$(gsettings get org.gnome.settings-daemon.plugins.media-keys custom-keybindings)

        # Add this slot to the list if not already there
        if [[ ! "$CURRENT" =~ "$SLOT" ]]; then
            # Remove the closing bracket, add our slot, close bracket
            if [ "$CURRENT" = "@as []" ] || [ "$CURRENT" = "[]" ]; then
                NEW_LIST="['/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/$SLOT/']"
            else
                NEW_LIST="${CURRENT%]}, '/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/$SLOT/']"
            fi
            gsettings set org.gnome.settings-daemon.plugins.media-keys custom-keybindings "$NEW_LIST"
        fi

        echo "✓ Keyboard shortcut set successfully!"
        echo "  Name: TFCBM Activate"
        echo "  Key: Ctrl+Esc"
        echo "  Command: $COMMAND"
        echo ""
        echo "Press Ctrl+Esc to activate your TFCBM window!"
        exit 0
    fi
done

echo "Error: No available custom keybinding slots found (tried custom0-custom99)"
exit 1
