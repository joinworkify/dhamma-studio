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

if [ ! -f "static/index.html" ]; then
    echo "ERROR: static/index.html was not found." >&2
    exit 1
fi

echo
echo "[1/5] Fetching bundled FFmpeg..."
./scripts/fetch_ffmpeg_mac.sh

echo
echo "[2/5] Syncing Python dependencies..."
uv sync --group build

echo
echo "[3/5] Cleaning previous build..."
rm -rf build dist

echo
echo "[4/5] Running PyInstaller..."
uv run pyinstaller dhamma_studio.spec --noconfirm --clean

APP_PATH="dist/Dhamma Studio.app"

echo
echo "[5/5] Checking build output..."
if [ -d "$APP_PATH" ]; then
    echo
    echo "BUILD SUCCESSFUL"
    echo "APP: $APP_PATH"
    echo
else
    echo "ERROR: $APP_PATH was not found." >&2
    exit 1
fi
