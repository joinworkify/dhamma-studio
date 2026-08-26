# dhamma-studio

A modern desktop application built with Python, pywebview, and FFmpeg designed for audio/caption QA verification, rich-text styling, and automated batch video generation with full Myanmar Unicode font support.

---

## ✨ Key Features

- **Audio & Caption QA:** Inspect audio synchronization with Myanmar text, calculate audio durations, and flag sync mismatches or missing files.
- **Audio Playback:** Built-in player with **Spacebar** hotkey support for rapid auditing.
- **Visual Text Styling Toolbar:** Apply inline highlight boxes (custom background & border colors) and text stroke outlines directly inside the editor.
- **Smart Dynamic Pagination:** Automatically splits long captions (capped at 4 lines per page) and syncs page durations weighted by character length.
- **Automated Video Generation:** Batch render video clips combining background images/videos, styled text overlays, and audio tracks via FFmpeg.
- **Background Music Integration:** Automatic BGM track detection (`assets/dhamma_bgm.mp3`) with custom start-offset trimming and volume balance.
- **Flexible Formats:** Supports Landscape (16:9 / 1920x1080) and Mobile/Shorts (9:16 / 1080x1920).
- **Customizable Styling:** Adjust overlay mode (Full vs Box), background opacity, text vertical positioning, font size, and line spacing.
- **Cross-Platform:** Native desktop GUI support across Linux, Windows, and macOS.

---

## 🛠️ System Prerequisites

### 1. FFmpeg Installation

FFmpeg must be installed and accessible in your system PATH:

- **Linux (Ubuntu / Debian / Mint):**
  ```bash
  sudo apt update && sudo apt install -y ffmpeg
  ```
  macOS (via Homebrew):
  ```
  brew install ffmpeg
  ```
  Windows (via Winget or Chocolatey):
  ```
  # Using Winget
  winget install Gyan.FFmpeg
  
  # Or using Chocolatey
  choco install ffmpeg
  ```
2. GUI Runtime Dependencies
  Linux (Ubuntu / Mint / Debian):
  Install WebKit2GTK or PyQt6 runtime dependencies:
    ```
    sudo apt install -y python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-webkit2-4.1
    ```
  macOS: Uses the built-in native WebKit engine (No extra installation required).

  Windows: Uses the built-in Microsoft Edge WebView2 runtime (Standard on Windows 10/11).
3. Myanmar Unicode Fonts
  Place your preferred Myanmar Unicode font (e.g., NamKhone Grand.ttf, Noto Sans Myanmar, or Pyidaungsu) inside the fonts/ directory or the project root.

🚀 Installation & Setup
1. Clone the Repository
```
Bash
git clone [https://github.com/joinworkify/dhamma-studio.git](https://github.com/joinworkify/dhamma-studio.git)
cd dhamma-studio
```
2. Set Up Virtual Environment
Linux / macOS:
```
Bash
python3 -m venv .venv
source .venv/bin/activate
```
Windows (Command Prompt / PowerShell):
```
PowerShell
python -m venv .venv
.venv\Scripts\activate
```
3. Install Python Dependencies
```
Bash
pip install -r requirements.txt
```
📁 Project Structure
```
Plaintext
├── assets/                 # Project assets (e.g. dhamma_bgm.mp3)
├── fonts/                  # Custom Myanmar TTF/OTF fonts
├── static/
│   ├── index.html          # Desktop GUI interface
│   └── app.js              # pywebview frontend-backend bridge
├── main.py                 # Application entry point & Backend API
├── video_engine.py         # FFmpeg video rendering & Pillow text drawing
├── requirements.txt        # Python package dependencies
├── .gitignore              # Git ignore rules
└── README.md
```
💻 Usage Guide
1. Launch the Application
```
Bash
python main.py
```
2. Tab 1: Audio & Caption QA
Click Browse CSV to load your dataset (requires caption and mp3 columns).

Click Browse Audios to select the directory containing your audio files.

Review rows sequentially:

Press Spacebar or click Play to listen to the audio track.

Use the Visual Toolbar to highlight text with custom fill/border boxes or apply text stroke outlines.

Click Save Row to apply changes.

Click Next Issue to quickly jump to duration or missing file warnings.

Click Export Cleaned CSV to export your formatted and verified dataset.

3. Tab 2: Video Generator
Switch to the Video Generator tab.

Select your Media Folder (images or videos), optional Corner Logo, and specify the destination Output Path.

Configure video preferences:

Format: Landscape (16:9) or Mobile/Shorts (9:16).

Overlay Mode: Full Video Overlay, Text Box Only, or None.

Position & Layout: Top, Center, or Bottom text alignment.

Typography: Font size, line spacing, overlay color, and opacity.

Click Start Video Rendering to generate the final synchronized video.

📦 Python Dependencies
pywebview - Cross-platform desktop GUI runtime

PyQt6 - GUI engine fallback for Linux/Windows

pygame - Audio playback engine

pandas - CSV parsing and dataset management

mutagen - Audio metadata and duration calculation

Pillow - Text layout, font rasterization, and overlay generation
