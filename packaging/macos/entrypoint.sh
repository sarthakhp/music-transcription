#!/bin/bash
# Contents/MacOS/MusicTranscriber — the macOS .app executable.
# Finds the bundled Python inside the .app bundle and runs launcher.py.

RESOURCES="$(cd "$(dirname "$0")/../Resources" && pwd)"

# Try Python binary names in order (python-build-standalone names by version)
PYTHON=""
for candidate in python3.12 python3.11 python3.13 python3; do
    if [ -x "$RESOURCES/python/bin/$candidate" ]; then
        PYTHON="$RESOURCES/python/bin/$candidate"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    osascript -e 'display alert "MusicTranscriber" message "Bundled Python not found. Please re-download the app." as critical'
    exit 1
fi

exec "$PYTHON" "$RESOURCES/launcher.py"
