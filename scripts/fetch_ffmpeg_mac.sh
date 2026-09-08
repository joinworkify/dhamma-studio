#!/usr/bin/env bash
# Downloads a static ffmpeg binary (GPL build, includes libx264) for bundling
# into the macOS .app via PyInstaller. Source: https://evermeet.cx/ffmpeg/
set -euo pipefail
cd "$(dirname "$0")/.."

DEST_DIR="vendor/ffmpeg/mac"
DEST_BIN="$DEST_DIR/ffmpeg"

if [ -f "$DEST_BIN" ]; then
    echo "ffmpeg already present at $DEST_BIN, skipping download."
    exit 0
fi

mkdir -p "$DEST_DIR"
TMP_ZIP="$(mktemp -t ffmpeg-mac-XXXX).zip"

echo "Downloading static ffmpeg (GPL build) from evermeet.cx..."
curl -L --fail -o "$TMP_ZIP" "https://evermeet.cx/ffmpeg/getrelease/ffmpeg/zip"

TMP_DIR="$(mktemp -d)"
unzip -q -o "$TMP_ZIP" -d "$TMP_DIR"
mv "$TMP_DIR/ffmpeg" "$DEST_BIN"
chmod +x "$DEST_BIN"
rm -rf "$TMP_ZIP" "$TMP_DIR"

echo "ffmpeg downloaded to $DEST_BIN"
"$DEST_BIN" -version | head -1
