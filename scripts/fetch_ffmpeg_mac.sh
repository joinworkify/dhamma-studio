#!/usr/bin/env bash
# Downloads a static arm64 (Apple Silicon) ffmpeg binary (GPL build, includes
# libx264) for bundling into the macOS .app via PyInstaller.
# Source: https://ffmpeg.martin-riedl.de/
set -euo pipefail
cd "$(dirname "$0")/.."

DEST_DIR="vendor/ffmpeg/mac"
DEST_BIN="$DEST_DIR/ffmpeg"

if [ -f "$DEST_BIN" ] && file "$DEST_BIN" | grep -q arm64; then
    echo "arm64 ffmpeg already present at $DEST_BIN, skipping download."
    exit 0
fi

rm -rf "$DEST_DIR"
mkdir -p "$DEST_DIR"
TMP_ZIP="$(mktemp -t ffmpeg-mac-XXXX).zip"

echo "Downloading static arm64 ffmpeg (GPL build)..."
curl -L --fail -o "$TMP_ZIP" "https://ffmpeg.martin-riedl.de/redirect/latest/macos/arm64/release/ffmpeg.zip"

TMP_DIR="$(mktemp -d)"
unzip -q -o "$TMP_ZIP" -d "$TMP_DIR"
mv "$TMP_DIR/ffmpeg" "$DEST_BIN"
chmod +x "$DEST_BIN"
rm -rf "$TMP_ZIP" "$TMP_DIR"

if ! file "$DEST_BIN" | grep -q arm64; then
    echo "ERROR: downloaded ffmpeg is not arm64." >&2
    exit 1
fi

echo "ffmpeg downloaded to $DEST_BIN"
"$DEST_BIN" -version | head -1
