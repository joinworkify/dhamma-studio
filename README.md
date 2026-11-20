# Dhamma Studio

> A desktop-friendly web application for creating Dhamma videos from audio, Excel-based captions, and background images.

Dhamma Studio helps users prepare caption timelines, automatically match background images, preview video layouts, translate captions, and render videos in landscape or mobile-short formats.

## Features

- Import audio files (`.mp3`, `.wav`)
- Import caption timelines from Excel (`.xlsx`, `.xls`)
- Upload background image folders
- CLIP-based semantic image matching
- Edit, update, and delete caption segments
- Preview captions and images
- YouTube Landscape (`16:9`)
- Mobile Shorts (`9:16`)
- 540p, 720p, and 1080p output
- Multiple language support
- Caption translation
- Optional background music (BGM)
- FFmpeg-based video rendering
- Download rendered MP4 videos
- Windows `.exe` build
- macOS `.app` build
- Linux application build

## Technology Stack

| Component | Technology |
|---|---|
| Backend | Python, FastAPI |
| Frontend | HTML, JavaScript, Tailwind CSS |
| Video Processing | FFmpeg |
| Image Processing | Pillow |
| Data Processing | Pandas, OpenPyXL |
| Image Matching | Sentence Transformers / CLIP |
| Package Management | uv |
| Packaging | PyInstaller |

## System Requirements

- Windows, Linux, or macOS
- Python 3.12
- Git
- uv
- FFmpeg
- Modern web browser
- Internet connection for initial dependency and model downloads

## Install the macOS app (no malware prompt)

Dhamma Studio is not yet signed with an Apple Developer ID, so a normal browser
download shows *"Apple could not verify Dhamma Studio is free of malware"*.
Install with this one-liner instead. Files fetched with `curl` carry no
quarantine flag, so macOS does not show the prompt:

```bash
curl -fsSL https://github.com/joinworkify/dhamma-studio/releases/latest/download/install-mac.sh | bash
```

(Apple Silicon only. You can read the script first: `scripts/install-mac.sh`.)

Already downloaded the DMG in a browser? Run once:
`xattr -cr "/Applications/Dhamma Studio.app"`

### Removing the warning for good (maintainers)

Needs a paid Apple Developer account. Create a *Developer ID Application*
certificate, then build with `ELECTROBUN_DEVELOPER_ID`, `ELECTROBUN_APPLEID`,
`ELECTROBUN_APPLEIDPASS` (app-specific password) and `ELECTROBUN_TEAMID` set.
`desktop/electrobun.config.ts` already turns on code signing and notarization
when those variables exist.

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/joinworkify/dhamma-studio.git
cd dhamma-studio
````

### 2. Install uv

#### Windows

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

#### Linux / macOS

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Check the installation:

```bash
uv --version
```

### 3. Install Dependencies

From the project directory:

```bash
uv sync
```

For development and packaging:

```bash
uv sync --all-groups
```

### 4. Install FFmpeg

#### Windows

Install FFmpeg and add the FFmpeg `bin` directory to the system PATH.

Check the installation:

```bash
ffmpeg -version
```

#### Ubuntu / Debian

```bash
sudo apt update
sudo apt install ffmpeg
```

#### macOS

```bash
brew install ffmpeg
```

Check the installation:

```bash
ffmpeg -version
```

## Run from Source

Start the application:

```bash
uv run python server.py
```

Then open the application in your browser:

```text
http://localhost:8000
```

## Build the Application

Dhamma Studio includes platform-specific build scripts for Windows, macOS, and Linux.

> Build the application on its target operating system. Windows applications should be built on Windows, macOS applications on macOS, and Linux applications on Linux.

### Windows

Open PowerShell inside the project directory:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\build_windows.ps1
```

Build output:

```text
dist\DhammaStudio\DhammaStudio.exe
```

> Distribute the entire `dist\DhammaStudio\` folder, not only the `.exe` file.

### macOS

Open Terminal inside the project directory:

```bash
chmod +x scripts/build_mac.sh
./scripts/build_mac.sh
```

Build output:

```text
dist/Dhamma Studio.app
```

The macOS build targets **Apple Silicon (arm64) only** and must be built on an Apple Silicon Mac. It bundles an arm64 FFmpeg and the CLIP model, so the finished app needs no Python, Homebrew, FFmpeg, or internet connection. If port 8000 is busy, the app picks a free port and opens the browser there. The app is not notarized: on another Mac, right-click it and choose Open the first time, or run `xattr -cr "Dhamma Studio.app"`.

### Linux

```bash
chmod +x scripts/build_linux.sh
./scripts/build_linux.sh
```

Build output:

```text
dist/DhammaStudio/DhammaStudio
```

Run the Linux application:

```bash
./dist/DhammaStudio/DhammaStudio
```

Then open:

```text
http://localhost:8000
```

## User Guide

For the complete setup and usage instructions, see:

[Dhamma Studio Final User Guide](https://docs.google.com/document/d/1TCIKESOf9TuirlvBxZ6Ymf1P-EurHMuVBlvE44HGGxQ/edit?usp=sharing)

The guide covers:

* Git clone and project setup
* Windows, macOS, and Linux builds
* Creating the Excel subtitle file using Gemini AI
* Gemini Excel generation prompt
* Excel timeline requirements
* Audio and Excel upload
* Background image matching
* Caption editing
* Translation
* Video settings
* Video rendering
* Downloading the final MP4
* Troubleshooting

## Project Structure

```text
dhamma-studio/
├── assets/
├── data/
├── fonts/
├── images/
├── output_renders/
├── scripts/
│   ├── build_linux.sh
│   ├── build_mac.sh
│   ├── build_windows.ps1
│   ├── fetch_clip_model.py
│   ├── fetch_ffmpeg_mac.sh
│   └── fetch_ffmpeg_windows.ps1
├── static/
├── uploads/
├── dhamma_studio.spec
├── pyproject.toml
├── requirements.txt
├── server.py
├── video_engine.py
└── uv.lock
```

## License

This project is intended for the Dhamma Studio video-generation workflow.

```
```

## Desktop app (Electrobun)

`desktop/` is an [Electrobun](https://electrobun.dev) shell: the UI is a Vite + Tailwind page bundled
into the app (`views://`), and the Python backend (`server.py`) runs as a sidecar the shell spawns.

```bash
./scripts/build_mac.sh          # build the PyInstaller backend into dist/DhammaStudio
export PATH="$HOME/.hutch/bin:$PATH"
cd desktop
hutch install
hutch run dev                   # dev run (uses the bundled sidecar if dist/DhammaStudio exists)
hutch run build                 # artifacts/macos-arm64-DhammaStudio.dmg
```
