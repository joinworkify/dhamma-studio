Dhamma Studio

> A desktop-friendly web application for creating Dhamma videos from audio, Excel-based captions, and background images.

Dhamma Studio helps users prepare caption timelines, match images to caption segments, preview video layouts, translate captions, and render videos in landscape or mobile-short formats.

## Features

- Import audio files (`.mp3`)
- Import caption timelines from Excel (`.xlsx`, `.xls`)
- Upload background image folders
- Automatically match images with caption segments
- CLIP-based semantic image matching
- Edit caption text directly in the interface
- Update and delete timeline rows
- Preview captions and images
- Support YouTube Landscape (`16:9`)
- Support Mobile Shorts (`9:16`)
- Support 540p, 720p, and 1080p output
- Support multiple languages
- Optional background music (BGM)
- Translate caption timelines
- Render videos using FFmpeg
- Download rendered MP4 videos

## Technology Stack

| Component | Technology |
|---|---|
| Backend | Python, FastAPI |
| Frontend | HTML, JavaScript, Tailwind CSS |
| Video Processing | FFmpeg |
| Image Processing | Pillow |
| Data Processing | Pandas, OpenPyXL |
| Image Matching | Sentence Transformers / CLIP |
| Package Management | uv / pip |
| Packaging | PyInstaller |

## System Requirements

- Windows, Linux, or macOS
- Python 3.12
- FFmpeg
- Modern web browser
- Internet connection for installing dependencies and model files

## Installation

### 1. Clone the Repository

```bash
git clone <YOUR_REPOSITORY_URL>
cd <YOUR_PROJECT_FOLDER>
````

Alternatively, download the repository as a ZIP file and extract it.

### 2. Install Python

Install Python **3.12**.

Check the installed version:

```bash
python --version
```

### 3. Install FFmpeg

FFmpeg is required to render the final video.

#### Windows

1. Download and extract FFmpeg.
2. Add the FFmpeg `bin` directory to the system PATH.
3. Open a new terminal.

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

Verify the installation:

```bash
ffmpeg -version
```

### 4. Create a Virtual Environment

#### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
```

#### Linux / macOS

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

### 5. Install Dependencies

Using `uv`:

```bash
uv sync
```

Using `pip`:

```bash
pip install -e .
```

## Running the Application

Start the FastAPI server:

```bash
python server.py
```

Open the application in your browser:

```text
http://localhost:8000
```

## Usage

### 1. Select Video Format

Choose one of the following formats:

* YouTube Landscape (`16:9`)
* Mobile Shorts (`9:16`)

### 2. Upload Audio

1. Select an MP3 audio file.
2. Upload the file.
3. Use the audio controls to play or pause the audio.

### 3. Upload Excel File

1. Select an Excel file.
2. Click **Load & Auto-Match**.
3. Review the imported caption timeline.

Make sure the Excel file contains valid start times, end times, and caption text.

### 4. Upload Images

1. Select the image folder.
2. Upload the background images.
3. Wait for the upload process to finish.
4. Run image matching.

### 5. Review and Edit Captions

You can edit caption text directly in the interface.

Check the following:

* Caption text
* Start time
* End time
* Line breaks
* Punctuation
* Matched image

### 6. Match Images

Click **Re-Match Images** to update image matching results.

Image matching may take longer when:

* The image folder contains many files.
* Images have high resolutions.
* The system uses CPU-based processing.

### 7. Translate Captions

1. Select the target language.
2. Click the translation option.
3. Review the translated captions.
4. Confirm the timeline before rendering.

### 8. Configure Video Settings

Available settings include:

* Video format
* Output quality
* Font size
* Line spacing
* Background dimming
* Caption box color
* Border color
* Outline color
* Background music

### 9. Render Video

1. Confirm all uploaded files.
2. Review the preview.
3. Click **Render Video**.
4. Wait until rendering is complete.

### 10. Download Video

After rendering is complete:

1. Click **Download Video**.
2. Save the generated MP4 file.
3. Check the video using a media player.

## Output Resolutions

### Landscape Format

| Quality | Resolution  |
| ------- | ----------- |
| 540p    | 960 × 540   |
| 720p    | 1280 × 720  |
| 1080p   | 1920 × 1080 |

### Mobile Format

| Quality | Resolution  |
| ------- | ----------- |
| 540p    | 540 × 960   |
| 720p    | 720 × 1280  |
| 1080p   | 1080 × 1920 |

## Excel Timeline Guidelines

Before uploading the Excel file:

* Confirm that all required columns exist.
* Check that start times are valid.
* Ensure end times are greater than start times.
* Check for empty captions.
* Check the segment order.
* Review overlapping timestamps.
* Confirm that the timeline matches the audio.

Incorrect timestamps can cause caption synchronization problems.

## Image Matching

The application uses caption information to find relevant background images.

The matching process includes:

1. Scanning image files.
2. Preparing image representations.
3. Comparing caption and image meaning.
4. Assigning images to timeline segments.
5. Using matched images during preview and rendering.

## Rendering

The video engine:

* Generates frames from the caption timeline.
* Draws captions using Pillow.
* Creates a frame sequence.
* Uses FFmpeg to encode the video.
* Uses the original audio track.
* Supports optional background music.
* Generates an MP4 output file.

Rendering speed depends on:

* CPU performance
* Output resolution
* Number of segments
* Image size
* Caption complexity
* FFmpeg encoder
* Audio duration

## API Endpoints

| Method | Endpoint                    | Description              |
| ------ | --------------------------- | ------------------------ |
| GET    | `/`                         | Load the frontend        |
| GET    | `/api/status`               | Check application status |
| POST   | `/api/upload_images_folder` | Upload images            |
| POST   | `/api/match_images`         | Match images             |
| POST   | `/api/upload_excel_sync`    | Upload Excel data        |
| POST   | `/api/switch_format`        | Change video format      |
| POST   | `/api/translate_timeline`   | Translate captions       |
| POST   | `/api/update_row`           | Update a timeline row    |
| POST   | `/api/delete_row`           | Delete a timeline row    |
| POST   | `/api/start_render`         | Start rendering          |
| GET    | `/api/download_video`       | Download the video       |
| GET    | `/api/get_image/{filename}` | Retrieve an image        |
| GET    | `/api/stream_audio`         | Stream audio             |
| GET    | `/api/get_logo`             | Retrieve the logo        |

## Project Structure

```text
Dhamma Studio/
├── server.py
├── video_engine.py
├── index.html
├── pyproject.toml
├── uploads/
├── media/
├── output/
└── README.md
```

## Development

Start the application from the project directory:

```bash
python server.py
```

Check the terminal for:

* Import errors
* Missing dependencies
* Excel processing errors
* Image matching errors
* FFmpeg errors
* Rendering failures

## Packaging

The project includes PyInstaller as a build dependency.

Before packaging, confirm that:

* Required files are included.
* FFmpeg is available.
* Fonts are included.
* Model files are available.
* Media folders are handled correctly.
* The application works on the target operating system.

## Troubleshooting

### Application Does Not Start

Check the Python version:

```bash
python --version
```

Activate the virtual environment and reinstall dependencies:

```bash
pip install -e .
```

Start the server again:

```bash
python server.py
```

### FFmpeg Is Not Recognized

Run:

```bash
ffmpeg -version
```

If the command is not found, install FFmpeg and add it to the system PATH.

### Browser Cannot Connect

Make sure the server is running and open:

```text
http://localhost:8000
```

Check the terminal for errors.

### Image Matching Is Slow

Possible causes:

* Large image files
* A large number of images
* CPU-based embedding generation
* Slow disk performance

Try reducing image sizes and removing unnecessary images.

### Captions Appear at the Wrong Time

Check the Excel file for:

* Incorrect start times
* Incorrect end times
* Overlapping segments
* Missing values
* Incorrect segment order

### Rendering Is Slow

Try the following:

* Use 540p or 720p for testing.
* Reduce image resolution.
* Test with a short audio file.
* Close unnecessary applications.
* Check the FFmpeg configuration.
* Avoid repeated rendering during development.

### Output Video Cannot Be Opened

Check:

* Whether FFmpeg completed successfully.
* Whether the output file was generated completely.
* Whether the source audio is valid.
* Whether the terminal displays an FFmpeg error.

## Limitations

* Rendering speed depends on hardware and FFmpeg configuration.
* Image matching may require significant CPU and memory resources.
* Incorrect Excel timestamps can affect synchronization.
* Translation results should be reviewed.
* Required fonts, models, and FFmpeg must be available.

```
```
