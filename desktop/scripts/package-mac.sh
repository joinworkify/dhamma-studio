#!/usr/bin/env bash
# Build the Electrobun app and package a DMG.
# With ELECTROBUN_DEVELOPER_ID set, Electrobun signs/notarizes itself.
# Otherwise the bundle is deep ad-hoc signed so macOS says "unidentified
# developer" (right-click > Open) instead of "damaged".
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.hutch/bin:$PATH"

# Stage timing. NOTE: "hutch run build" ends with Electrobun zstd-compressing
# the whole .app (~2 GB tar, level 19, single thread) for the auto-update
# artifact. That step alone takes ~8-10 min and is not needed for a DMG.
T0=$SECONDS
mark() { echo "[$(date +%H:%M:%S)] $1 (elapsed $((SECONDS - T0))s)"; }
trap 'mark "done/exit"' EXIT

mark "hutch build start (vite + electrobun + zstd)"
hutch run build
mark "hutch build finished"

APP="build/stable-macos-arm64/Dhamma Studio.app"
if [ -z "${ELECTROBUN_DEVELOPER_ID:-}" ]; then
  codesign --force --deep --sign - "$APP"
  codesign --verify --deep --strict "$APP"
  STAGE="$(mktemp -d)"
  ditto "$APP" "$STAGE/Dhamma Studio.app"
  ln -s /Applications "$STAGE/Applications"
  rm -f artifacts/macos-arm64-DhammaStudio.dmg
  hdiutil create -volname "Dhamma Studio" -srcfolder "$STAGE" -ov -format UDZO artifacts/macos-arm64-DhammaStudio.dmg
  rm -rf "$STAGE"
fi
ls -lh artifacts/macos-arm64-DhammaStudio.dmg
