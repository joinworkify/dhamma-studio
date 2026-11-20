#!/usr/bin/env bash
# Build Dhamma Studio.app for macOS.
set -euo pipefail

cd "$(dirname "$0")/.."

# --- stage timing: prints elapsed per stage and warns when one runs long ---
SECONDS=0
_STAGE_START=0
_STAGE_NAME=""
SLOW_WARN_SECS="${SLOW_WARN_SECS:-300}"   # warn if a stage exceeds 5 min
_end_stage() {
    if [ -n "$_STAGE_NAME" ]; then
        local took=$((SECONDS - _STAGE_START))
        local flag=""
        [ "$took" -gt "$SLOW_WARN_SECS" ] && flag="  <-- SLOW (> ${SLOW_WARN_SECS}s)"
        echo "    [time] ${_STAGE_NAME}: ${took}s${flag}"
    fi
}
stage() {
    _end_stage
    _STAGE_NAME="$1"
    _STAGE_START=$SECONDS
    echo
    echo "[$(date +%H:%M:%S)] $1"
}
trap '_end_stage; echo "    [time] total: ${SECONDS}s"' EXIT

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

stage "[1/6] Fetching bundled FFmpeg..."
./scripts/fetch_ffmpeg_mac.sh

stage "[2/6] Syncing Python dependencies..."
uv sync --group build

stage "[3/6] CLIP model (downloaded by the app on first launch; BUNDLE_CLIP=1 to bundle)"
if [ "${BUNDLE_CLIP:-0}" = "1" ]; then
    uv run python scripts/fetch_clip_model.py
fi

stage "[4/6] Cleaning previous build..."
rm -rf build dist

stage "[5/6] Running PyInstaller..."
uv run pyinstaller dhamma_studio.spec --noconfirm --clean

APP_PATH="dist/Dhamma Studio.app"

stage "[6/6] Checking build output..."
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
