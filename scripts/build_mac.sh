#!/usr/bin/env bash
# Build Dhamma Studio.app for macOS.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "=== Dhamma Studio macOS Build ==="

if ! command -v uv >/dev/null 2>&1; then
    echo "ERROR: uv not found. Install uv first." >&2
    exit 1
fi

if [ ! -f "server.py" ]; then
    echo "ERROR: server.py was not found in the project root." >&2
    exit 1
fi

if [ "$(uname -m)" != "arm64" ]; then
    echo "ERROR: build on an Apple Silicon (arm64) Mac." >&2
    exit 1
fi

if [ ! -f "assets/icon.icns" ]; then
    echo "ERROR: assets/icon.icns was not found." >&2
    exit 1
fi

if [ ! -f "static/index.html" ]; then
    echo "ERROR: static/index.html was not found." >&2
    exit 1
fi

echo
echo "[1/6] Fetching bundled FFmpeg..."
./scripts/fetch_ffmpeg_mac.sh

echo
echo "[2/6] Syncing Python dependencies..."
uv sync --group build

echo
echo "[3/6] Bundling CLIP model for offline use..."
uv run python scripts/fetch_clip_model.py

echo
echo "[4/6] Cleaning previous build..."
rm -rf build dist

echo
echo "[5/6] Running PyInstaller..."
uv run pyinstaller dhamma_studio.spec --noconfirm --clean

APP_PATH="dist/Dhamma Studio.app"

echo
echo "[6/6] Checking build output..."
if [ -d "$APP_PATH" ]; then
    echo
    echo "BUILD SUCCESSFUL"
    echo "APP: $APP_PATH"
    file "$APP_PATH/Contents/MacOS/DhammaStudio"
    echo
else
    echo "ERROR: $APP_PATH was not found." >&2
    exit 1
fi
