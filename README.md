# dhamma-studio

A modern desktop application built with Python, pywebview, and FFmpeg designed for audio/caption QA verification, rich-text styling, and automated batch video generation with full Myanmar Unicode font support.

---
## ✨ Key Features

- **Audio & Caption QA:** Inspect audio synchronization with Myanmar text, calculate audio durations, and flag sync mismatches or missing files.
- **Audio Playback:** Built-in player with **Spacebar** hotkey support for rapid auditing.
- **Visual Text Styling Toolbar:** Apply inline highlight boxes (custom background & border colors) and text stroke outlines directly inside the live editor.
- **AI Semantic Image Matching:** Integrates OpenAI's CLIP model (`clip-ViT-B-32`) to analyze caption semantics and automatically pair each scene with the most visually relevant image/video.
- **Incremental Embedding Cache:** Scans media assets incrementally (`.clip_embeddings_cache.pt`), caching vectors locally so subsequent renders start instantly.
- **Intelligent Non-Duplication:** Tracks used media paths across scenes to avoid repetitive back-to-back imagery while recycling assets dynamically when depleted.
- **Continuous Line Stream Engine:** Eliminates orphaned single lines across slide transitions by maintaining a continuous line queue (e.g., exactly 3 lines per slide) and seamlessly cross-syncing audio slices across CSV rows.
- **Intro Clip Isolation & BGM Toggle:** Isolates title/intro scenes when background music is enabled, with user-controlled BGM toggle support in the UI.
- **Flexible Formats:** Supports Landscape (16:9 / 1920x1080) and Mobile/Shorts (9:16 / 1080x1920 with background blur effects).
- **Customizable Styling:** Adjust overlay mode (Full vs Box), background opacity, text vertical positioning, font size, line spacing, and corner logo placement with safe margins.
- **Cross-Platform:** Native desktop GUI support across Linux, Windows, and macOS with automatic hardware encoder detection (NVENC, VideoToolbox, QSV, and CPU libx264).

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
2. Set Up Environment & Install Dependencies

**Option A — uv (recommended):**
Project is pinned to Python 3.12 via `.python-version` / `pyproject.toml`. [Install uv](https://docs.astral.sh/uv/getting-started/installation/) if you don't have it, then:
```
Bash
uv sync
```
This creates `.venv` with Python 3.12 and installs all locked dependencies. Run the app with:
```
Bash
uv run python main.py
```

**Option B — pip + venv:**
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
Install Python Dependencies:
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
├── pyproject.toml          # uv project config (pinned to Python 3.12)
├── dhamma_studio.spec      # PyInstaller build spec
├── scripts/                # Build & packaging scripts (see below)
├── .gitignore              # Git ignore rules
└── README.md
```

---
## 📦 Building a Standalone App (macOS / Windows)

These scripts package the app (via [uv](https://docs.astral.sh/uv/) + PyInstaller) into a double-clickable
`.app` (macOS) or folder with `.exe` (Windows) — no Python install required to run it.

**macOS:**
```bash
./scripts/build_mac.sh
```
Output: `dist/Dhamma Studio.app`

**Windows** (run on Windows — PyInstaller does not cross-compile):
```powershell
.\scripts\build_windows.ps1
```
Output: `dist\DhammaStudio\DhammaStudio.exe`

Both scripts also fetch and bundle a static **ffmpeg** binary automatically
(`scripts/fetch_ffmpeg_mac.sh` / `scripts/fetch_ffmpeg_windows.ps1`) so the packaged
app works without ffmpeg installed on the target machine. The bundled ffmpeg build
includes libx264 and is licensed **GPL** — keep that in mind if you redistribute
the built app. Downloaded binaries live in `vendor/ffmpeg/` (gitignored, not committed).

Note: the first run of AI Semantic Image Matching downloads the CLIP model
(`clip-ViT-B-32`, ~350MB) from Hugging Face on demand — the packaged app still needs
internet access the first time that feature is used.

---
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

Click Save Row to apply modifications.

Click Next Issue to jump directly to duration mismatches or missing file warnings.

Click Export Cleaned CSV to export your formatted and verified dataset.

3. Tab 2: Video Generator
Switch to the Video Generator tab.

Select your Media Folder (images or videos), optional Corner Logo, and specify the destination Output Path.

Configure video preferences:

Format: Landscape (16:9) or Mobile/Shorts (9:16).

Lines Per Page: Set fixed line count (e.g., 2 or 3 lines) to maintain consistent row layouts.

Position & Layout: Top, Center, or Bottom text alignment.

Typography & Overlay: Font size, line spacing, overlay color, and opacity.

Background Music: Toggle the BGM checkbox to enable or disable intro audio mixing.

Click Start Video Rendering to generate the final synchronized video.

📦 Python Dependencies
pywebview - Cross-platform desktop GUI runtime

PyQt6 - GUI engine fallback for Linux/Windows

sentence-transformers & torch - CLIP-based AI vision and semantic text-to-image matching

scikit-learn - Similarity score calculations and vector indexing

pygame - Low-latency audio playback engine for QA auditing

pandas - CSV parsing, batch data traversal, and dataset management

mutagen - Audio metadata inspection and duration calculation

Pillow - Text layout, RAQM complex script font shaping, and overlay generation
