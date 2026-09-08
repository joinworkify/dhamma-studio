#!/usr/bin/env bash
# Build "Dhamma Studio.app" for macOS via PyInstaller + uv.
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v uv >/dev/null 2>&1; then
    echo "uv not found. Install it: https://docs.astral.sh/uv/getting-started/installation/" >&2
    exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "Warning: ffmpeg not found on PATH. It is NOT bundled into the .app —" >&2
    echo "users must install it separately (brew install ffmpeg) for rendering to work." >&2
fi

echo "Syncing dependencies (including build group)..."
uv sync --group build

echo "Cleaning previous build output..."
rm -rf build dist

echo "Building Dhamma Studio.app..."
uv run pyinstaller dhamma_studio.spec --noconfirm

APP_PATH="dist/Dhamma Studio.app"
if [ -d "$APP_PATH" ]; then
    echo "Build succeeded: $APP_PATH"
else
    echo "Build finished but $APP_PATH was not found." >&2
    exit 1
fi
