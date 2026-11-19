#!/usr/bin/env bash
# Build the Electrobun app and package a DMG.
# With ELECTROBUN_DEVELOPER_ID set, Electrobun signs/notarizes itself.
# Otherwise the bundle is deep ad-hoc signed so macOS says "unidentified
# developer" (right-click > Open) instead of "damaged".
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.hutch/bin:$PATH"

hutch run build

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
