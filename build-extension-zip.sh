#!/bin/sh
set -e

SOURCE_DIR="$1"
OUTPUT_FILE="$2"

cd "$SOURCE_DIR/gnome-extension"
zip -r "$OUTPUT_FILE" \
    extension.js \
    metadata.json \
    tfcbm.svg \
    src/ \
    schemas/ \
    -x "*.md" "*.sh" "test/*" "package.json"
