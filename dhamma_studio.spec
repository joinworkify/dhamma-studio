# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

block_cipher = None

APP_NAME = "Dhamma Studio"
ICON_ICNS = "assets/icon.icns"
ICON_ICO = "assets/icon.ico"

# Read-only resources that the application needs at runtime.
datas = [
    ("static", "static"),
    ("fonts", "fonts"),
    ("assets", "assets"),
]

binaries = []
hiddenimports = []

# Optional bundled FFmpeg.
# Windows/macOS fetch scripts place FFmpeg under vendor/ffmpeg/<platform>/.
# Linux can use the system ffmpeg from PATH unless a bundled binary is present.
if sys.platform == "darwin":
    ffmpeg_src = Path("vendor/ffmpeg/mac/ffmpeg")
elif sys.platform == "win32":
    ffmpeg_src = Path("vendor/ffmpeg/windows/ffmpeg.exe")
else:
    ffmpeg_src = Path("vendor/ffmpeg/linux/ffmpeg")

if ffmpeg_src.exists():
    datas.append((str(ffmpeg_src), "ffmpeg-bin"))
else:
    print(
        f"INFO: {ffmpeg_src} not found. "
        "The application will use ffmpeg from PATH at runtime."
    )

# Sentence Transformers / Torch contain dynamic imports, native libraries,
# and package data that PyInstaller may not discover automatically.
for pkg in (
    "sentence_transformers",
    "transformers",
    "tokenizers",
    "torch",
    "sklearn",
    "scipy",
):
    pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(pkg)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hiddenimports

a = Analysis(
    ["server.py"],
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
    console=True,
    icon=(
        ICON_ICO
        if sys.platform == "win32" and Path(ICON_ICO).exists()
        else None
    ),
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