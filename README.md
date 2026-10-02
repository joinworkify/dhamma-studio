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

[Dhamma Studio Final User Guide](./Dhamma_Studio_Final_NonDeveloper_Guide_Final.docx)

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
