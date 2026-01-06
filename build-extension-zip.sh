#!/bin/sh
set -e

SOURCE_DIR="$1"
OUTPUT_DIR="$2"
OUTPUT_NAME="$3"

cd "$SOURCE_DIR/gnome-extension"
zip -r "$OUTPUT_DIR/$OUTPUT_NAME" \
    extension.js \
    metadata.json \
    tfcbm.svg \
    src/ \
    schemas/ \
    -x "*.md" "*.sh" "test/*" "package.json"
