#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "=== Dhamma Studio Linux Build ==="

if ! command -v uv >/dev/null 2>&1; then
    echo "ERROR: uv is not installed."
    echo "Install uv first, then run this script again."
    exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "WARNING: ffmpeg was not found on PATH."
    echo "The build can continue, but rendering will not work until ffmpeg is installed."
else
    echo "FFmpeg: $(command -v ffmpeg)"
    ffmpeg -version | head -1
fi

echo "Syncing dependencies..."
uv sync --group build

echo "Cleaning previous build output..."
rm -rf build dist

echo "Building Linux application..."
uv run pyinstaller dhamma_studio.spec --noconfirm

APP_PATH="dist/DhammaStudio/DhammaStudio"

if [ -f "$APP_PATH" ]; then
    chmod +x "$APP_PATH"
    echo
    echo "Build succeeded:"
    echo "  $APP_PATH"
    echo
    echo "Run it with:"
    echo "  $APP_PATH"
else
    echo
    echo "ERROR: Linux executable was not found at:"
    echo "  $APP_PATH"
    exit 1
fi
