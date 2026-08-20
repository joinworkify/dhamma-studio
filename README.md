# dhamma-studio

A modern desktop application built with Python, pywebview, and FFmpeg designed for audio/caption QA verification and automated batch video generation with full Myanmar Unicode font support.

---

## ✨ Key Features

- **Audio & Caption QA:** Inspect audio synchronization with Myanmar text, calculate duration, and edit captions row-by-row.
- **Audio Playback:** Built-in player with **Spacebar** hotkey shortcut support.
- **Automated Video Generation:** Batch render videos by combining background images, custom text overlays, and audio tracks via FFmpeg.
- **Flexible Formats:** Supports Landscape (16:9 / 1920x1080) and Mobile/Shorts (9:16 / 1080x1920).
- **Customizable Styling:** Adjust overlay mode (Full vs Box), background opacity, text position, font size, and line spacing.
- **Cross-Platform:** Native GUI support across Linux, Windows, and macOS.

---

## 🛠️ System Prerequisites

### 1. FFmpeg Installation

FFmpeg must be installed and available in your system PATH:

- **Linux (Ubuntu / Debian / Mint):**
  ```bash
  sudo apt update && sudo apt install -y ffmpeg

```

* **macOS (via Homebrew):**
```bash
brew install ffmpeg

```


* **Windows (via Winget or Chocolatey):**
```powershell
# Using Winget
winget install Gyan.FFmpeg

# Or using Chocolatey
choco install ffmpeg

```



### 2. GUI Runtime Dependencies

* **Linux (Ubuntu / Mint / Debian):**
Install the required WebKit2GTK system libraries:
```bash
sudo apt install -y python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-webkit2-4.1

```


* **macOS:** Uses the built-in native WebKit engine (No extra installation required).
* **Windows:** Uses the built-in Microsoft Edge WebView2 runtime (Standard on Windows 10/11).

### 3. Myanmar Unicode Fonts

Place your preferred Myanmar Unicode font (e.g., `NamKhone Grand.ttf`, `Noto Sans Myanmar`, or `Pyidaungsu`) inside the project root or the `fonts/` directory.

---

## 🚀 Installation & Setup

### 1. Clone the Repository

```bash
git clone [https://github.com/joinworkify/dhamma-studio.git](https://github.com/joinworkify/dhamma-studio.git)
cd dhamma-studio

```

### 2. Set Up Virtual Environment

* **Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate

```


* **Windows (Command Prompt / PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\activate

```



### 3. Install Python Dependencies

```bash
pip install -r requirements.txt

```

---

## 📁 Project Structure

```text
├── fonts/                  # Custom Myanmar TTF/OTF fonts
├── static/
│   ├── index.html          # Desktop GUI interface (Tailwind CSS)
│   ├── tailwind.min.css    # Local Tailwind styling
│   └── app.js              # pywebview frontend-backend bridge
├── main.py                 # Application entry point & Backend API
├── video_engine.py         # FFmpeg video rendering & Pillow text drawing
├── requirements.txt        # Python package dependencies
├── .gitignore              # Git ignore rules
└── README.md

```

---

## 💻 Usage Guide

### 1. Launch the Application

```bash
python main.py

```

### 2. Tab 1: Audio & Caption QA

1. Click **Browse CSV** to load your dataset (requires `caption` and `mp3` columns).
2. Click **Browse Audios** to select the directory containing your audio files.
3. Review rows sequentially:
* Press **Spacebar** or click **Play** to listen to the audio track.
* Edit the MP3 filename or Myanmar caption directly.
* Click **Save Row** to apply changes.
* Click **Next Issue** to jump to duration/missing file warnings.


4. Click **Export Cleaned CSV** to save your verified dataset.

### 3. Tab 2: Video Generator

1. Switch to the **Video Generator** tab.
2. Select your **Images Directory** and specify the destination **Save Output Path**.
3. Configure your video rendering preferences:
* **Format:** Landscape (16:9) or Mobile/Shorts (9:16).
* **Overlay Mode:** Full Video Overlay or Text Box Only.
* **Text Position:** Top, Middle, or Bottom.
* **Styling:** Background color, opacity percentage, font size, and line spacing.


4. Click **Start Video Rendering** to begin batch processing.

---

## 📦 Python Dependencies

* `pywebview` - Cross-platform desktop GUI runtime
* `pygame` - Audio playback engine
* `pandas` - CSV parsing and dataset management
* `mutagen` - Audio metadata and duration calculation
* `Pillow` - Text measurement and image overlay synthesis
* `imageio-ffmpeg` - Standalone fallback FFmpeg wrapper

```

```
