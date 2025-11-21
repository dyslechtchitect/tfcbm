#!/bin/bash
# Wrapper script to activate TFCBM window via GApplication action
# GApplication actions are properly integrated with GNOME Shell and support activation tokens

# Call the show-window action on the GApplication using org.gtk.Actions
gdbus call --session \
    --dest org.tfcbm.ClipboardManager \
    --object-path /org/tfcbm/ClipboardManager \
    --method org.gtk.Actions.Activate \
    "show-window" "[]" "{}"
