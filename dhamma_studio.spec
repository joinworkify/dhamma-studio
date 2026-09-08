# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

block_cipher = None

APP_NAME = "Dhamma Studio"
ICON_ICNS = "assets/icon.icns"
ICON_ICO = "assets/icon.ico"

datas = [("static", "static"), ("fonts", "fonts")]
binaries = []
hiddenimports = []

# Bundled ffmpeg (fetched by scripts/fetch_ffmpeg_mac.sh or
# scripts/fetch_ffmpeg_windows.ps1 into vendor/ffmpeg/<platform>/) so the
# packaged app doesn't depend on ffmpeg being on the user's PATH.
if sys.platform == "darwin":
    ffmpeg_src = Path("vendor/ffmpeg/mac/ffmpeg")
elif sys.platform == "win32":
    ffmpeg_src = Path("vendor/ffmpeg/windows/ffmpeg.exe")
else:
    ffmpeg_src = Path("vendor/ffmpeg/linux/ffmpeg")

if ffmpeg_src.exists():
    # Added via `datas`, not `binaries`: it's a standalone CLI tool to copy
    # as-is, not a shared library PyInstaller should rewrite link paths for.
    datas.append((str(ffmpeg_src), "ffmpeg-bin"))
else:
    print(f"WARNING: {ffmpeg_src} not found — building without bundled ffmpeg "
          f"(app will fall back to ffmpeg on PATH at runtime).")

# These packages do dynamic/lazy imports and ship non-.py data (model configs,
# compiled extensions) that PyInstaller's static analysis can't see on its own.
for pkg in (
    "sentence_transformers",
    "transformers",
    "tokenizers",
    "torch",
    "sklearn",
    "scipy",
    "PyQt6",
):
    pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(pkg)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hiddenimports

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME.replace(" ", ""),
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon=ICON_ICO if sys.platform == "win32" and Path(ICON_ICO).exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name=APP_NAME.replace(" ", ""),
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon=ICON_ICNS if Path(ICON_ICNS).exists() else None,
        bundle_identifier="com.joinworkify.dhammastudio",
        info_plist={
            "NSHighResolutionCapable": True,
            "CFBundleShortVersionString": "0.1.0",
        },
    )
