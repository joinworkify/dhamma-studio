import shutil

# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

block_cipher = None

APP_NAME = "Dhamma Studio"
ICON_ICNS = "assets/icon.icns"
ICON_ICO = "assets/icon.ico"

# Read-only resources required at runtime.
datas = [
    ("static", "static"),
    ("fonts", "fonts"),
    ("assets", "assets"),
]

# The CLIP model is NOT bundled (keeps the installer ~400 MB smaller); the app
# downloads it on first launch. Set BUNDLE_CLIP=1 to bundle it for offline builds.
clip_dir = Path("vendor/models/clip-ViT-B-32")

if os.environ.get("BUNDLE_CLIP") == "1" and clip_dir.exists():
    datas.append((str(clip_dir), "models/clip-ViT-B-32"))
    print(f"INFO: Bundling CLIP model from {clip_dir}")
else:
    print("INFO: CLIP model not bundled; it downloads on first launch.")

binaries = []
hiddenimports = []

# Bundle FriBiDi DLL for Windows Myanmar text rendering.
if sys.platform == "win32":
    fribidi_dll = Path(
        "runtime/windows/x64/libfribidi-0.dll"
    )

    if fribidi_dll.exists():
        binaries.append((
            str(fribidi_dll),
            "runtime/windows/x64"
        ))
        print(f"INFO: Bundling FriBiDi DLL: {fribidi_dll}")
    else:
        raise FileNotFoundError(
            f"Required FriBiDi DLL not found: {fribidi_dll}"
        )

# Bundle libfribidi for macOS (Pillow RAQM -> correct Myanmar shaping).
if sys.platform == "darwin":
    for _p in (
        Path("/opt/homebrew/lib/libfribidi.0.dylib"),
        Path("/usr/local/lib/libfribidi.0.dylib"),
    ):
        if _p.exists():
            # Pillow dlopens the *unversioned* name "libfribidi.dylib".
            _fb = Path("build/fribidi/libfribidi.dylib")
            _fb.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(_p.resolve(), _fb)
            binaries.append((str(_fb), "runtime/mac"))
            print(f"INFO: Bundling FriBiDi dylib: {_p}")
            break
    else:
        raise FileNotFoundError("Run: brew install fribidi")

# Optional bundled FFmpeg.
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

# Collect Sentence Transformers and Torch dependencies.
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

# Analyze application.
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

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher
)

# Build executable.
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
    target_arch="arm64" if sys.platform == "darwin" else None,
    icon=(
        ICON_ICO
        if sys.platform == "win32" and Path(ICON_ICO).exists()
        else None
    ),
)

# Collect application files.
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name=APP_NAME.replace(" ", ""),
)

# macOS application bundle.
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon=ICON_ICNS if Path(ICON_ICNS).exists() else None,
        bundle_identifier="com.joinworkify.dhammastudio",
        info_plist={
            "NSHighResolutionCapable": True,
            "CFBundleShortVersionString": "0.4.2",
        },
    )
