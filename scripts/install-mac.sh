#!/usr/bin/env bash
# Install the latest Dhamma Studio for macOS (Apple Silicon) without the
# "Apple could not verify ... is free of malware" prompt.
#
# Files downloaded with curl are not marked with macOS's quarantine flag, so
# Gatekeeper does not block the first launch of the (ad-hoc signed) app.
#
#   curl -fsSL https://github.com/joinworkify/dhamma-studio/releases/latest/download/install-mac.sh | bash
#
set -euo pipefail

REPO="joinworkify/dhamma-studio"
ASSET="DhammaStudio-macOS-arm64.dmg"
INSTALL_DIR="${INSTALL_DIR:-/Applications}"
APP_NAME="Dhamma Studio.app"

if [ "$(uname -s)" != "Darwin" ] || [ "$(uname -m)" != "arm64" ]; then
    echo "This installer is for Apple Silicon Macs (arm64) only." >&2
    exit 1
fi

TMP="$(mktemp -d)"
MOUNT=""
cleanup() {
    [ -n "$MOUNT" ] && hdiutil detach "$MOUNT" -quiet 2>/dev/null || true
    rm -rf "$TMP"
}
trap cleanup EXIT

echo "Downloading Dhamma Studio (latest release)..."
curl -fL --progress-bar -o "$TMP/$ASSET" \
    "https://github.com/$REPO/releases/latest/download/$ASSET"

echo "Mounting disk image..."
MOUNT="$TMP/mnt"
mkdir -p "$MOUNT"
hdiutil attach "$TMP/$ASSET" -nobrowse -readonly -quiet -mountpoint "$MOUNT"

if [ ! -d "$MOUNT/$APP_NAME" ]; then
    echo "ERROR: $APP_NAME not found in the disk image." >&2
    exit 1
fi

echo "Installing to $INSTALL_DIR ..."
mkdir -p "$INSTALL_DIR"
rm -rf "$INSTALL_DIR/$APP_NAME"
ditto "$MOUNT/$APP_NAME" "$INSTALL_DIR/$APP_NAME"

# Belt and braces: make sure no quarantine flag is present.
xattr -dr com.apple.quarantine "$INSTALL_DIR/$APP_NAME" 2>/dev/null || true

echo
echo "Installed: $INSTALL_DIR/$APP_NAME"
echo "Open it from Applications. The first start takes about a minute."
if [ "$INSTALL_DIR" = "/Applications" ]; then
    open "$INSTALL_DIR/$APP_NAME"
fi
