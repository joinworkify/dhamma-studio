import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import pandas as pd
import mutagen

import video_engine

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
IMAGES_DIR = UPLOAD_DIR / "images"
STATIC_DIR = BASE_DIR / "static"
UPLOAD_DIR.mkdir(exist_ok=True)
IMAGES_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)

app = FastAPI(title="Dhamma Studio")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

SESSION = {
    "audio_path": "",
    "media_dir": str(IMAGES_DIR),
    "logo_path": "",
    "rows": [],
    "progress_msg": "Idle",
    "progress_pct": 0,
    "is_rendering": False,
    "last_video": "",
    "cached_images": [],
    "image_embeddings": None
}


def set_progress(msg: str, pct: int):
    SESSION["progress_msg"] = msg
    SESSION["progress_pct"] = pct


def get_user_downloads_dir():
    home = Path.home()
    dl_candidates = [
        home / "Downloads",
        home / "downloads",
    ]
    for c in dl_candidates:
        if c.exists() and c.is_dir():
            return c
    return home / "Downloads"


def detect_initial_speech_offset(audio_path, threshold_db=-35):
    cmd = [
        video_engine.FFMPEG_BIN, "-y", "-hide_banner",
        "-i", str(audio_path),
        "-af", f"silencedetect=noise={threshold_db}dB:d=0.2",
        "-f", "null", "-"
    ]
    try:
        res = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True, timeout=20)
        for line in res.stderr.splitlines():
            if "silence_end:" in line:
                m = re.search(r"silence_end:\s*([0-9.]+)", line)
                if m:
                    return max(0.0, float(m.group(1)))
        return 0.0
    except Exception:
        return 0.0


def detect_audio_pauses_precise(audio_path, min_silence_len=0.25, threshold_db=-34):
    cmd = [
        video_engine.FFMPEG_BIN, "-y", "-hide_banner",
        "-i", str(audio_path),
        "-af", f"silencedetect=noise={threshold_db}dB:d={min_silence_len}",
        "-f", "null", "-"
    ]
    try:
        res = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True, timeout=30)
        pauses = []
        for line in res.stderr.splitlines():
            if "silence_end:" in line:
                m = re.search(r"silence_end:\s*([0-9.]+)", line)
                if m:
                    pauses.append(float(m.group(1)))
        return sorted(pauses)
    except Exception:
        return []


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    with open(STATIC_DIR / "index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/api/status")
async def get_status():
    return {
        "msg": SESSION["progress_msg"],
        "pct": SESSION["progress_pct"],
        "is_rendering": SESSION["is_rendering"],
        "total_rows": len(SESSION["rows"])
    }


@app.post("/api/upload_images_folder")
async def upload_images_folder(files: List[UploadFile] = File(...)):
    shutil.rmtree(IMAGES_DIR, ignore_errors=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    saved_files = []
    for f in files:
        if f.filename:
            dest = IMAGES_DIR / Path(f.filename).name
            with open(dest, "wb") as buffer:
                shutil.copyfileobj(f.file, buffer)
            if dest.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]:
                saved_files.append(dest)

    SESSION["media_dir"] = str(IMAGES_DIR)
    set_progress("AI indexing background images...", 10)
    SESSION["cached_images"], SESSION["image_embeddings"] = video_engine.scan_and_index_images(
        SESSION["media_dir"], saved_files, progress_cb=set_progress
    )
    set_progress("Images folder ready!", 100)
    return {"success": True, "count": len(saved_files)}


@app.post("/api/upload_assets")
async def upload_assets(
    audio: UploadFile = File(...),
    text: UploadFile = File(...),
    logo: Optional[UploadFile] = File(None)
):
    try:
        set_progress("Processing audio & transcript...", 10)

        audio_path = UPLOAD_DIR / audio.filename
        with open(audio_path, "wb") as f:
            shutil.copyfileobj(audio.file, f)
        SESSION["audio_path"] = str(audio_path)

        if logo and logo.filename:
            logo_path = UPLOAD_DIR / logo.filename
            with open(logo_path, "wb") as f:
                shutil.copyfileobj(logo.file, f)
            SESSION["logo_path"] = str(logo_path)
        else:
            SESSION["logo_path"] = ""

        text_content = (await text.read()).decode("utf-8-sig", errors="ignore")

        try:
            audio_info = mutagen.File(str(audio_path))
            total_dur = float(audio_info.info.length)
        except Exception:
            total_dur = 60.0

        font = video_engine.get_render_font(48)
        max_pixel_w = int(1920 * 0.82)

        screens = video_engine.split_into_screens_and_lines(
            text_content, max_pixel_w, font, max_lines_per_screen=4
        )
        if not screens:
            return JSONResponse({"success": False, "error": "No valid text sentences found."}, status_code=400)

        detected_pauses = detect_audio_pauses_precise(audio_path)
        title_dur = 4.5
        remaining_dur = max(1.0, total_dur - title_dur)

        body_screens = screens[1:]
        body_weights = [sum(len(l) for l in lines) + (len(lines) * 6) for lines in body_screens]
        total_w = sum(body_weights) or 1
        body_durations = [(w / total_w) * remaining_dur for w in body_weights]

        rows = []
        used_images = set()

        # Connect the first image to Segment 0
        first_img_url = ""
        if SESSION["cached_images"]:
            first_img_url = f"/api/get_image/{SESSION['cached_images'][0].name}"
            used_images.add(SESSION["cached_images"][0])

        title_text = "\n".join(screens[0])
        rows.append({
            "index": 0,
            "caption": title_text,
            "lines": screens[0],
            "start_time": 0.0,
            "end_time": round(title_dur, 2),
            "duration": round(title_dur, 2),
            "matched_img": first_img_url
        })

        acc = title_dur
        for idx, (lines, dur) in enumerate(zip(body_screens, body_durations), start=1):
            st = round(acc, 2)
            target_end = acc + dur

            if detected_pauses:
                valid = [p for p in detected_pauses if p > st + 1.0]
                if valid:
                    closest = min(valid, key=lambda p: abs(p - target_end))
                    et = round(closest, 2) if abs(closest - target_end) <= 2.5 else round(min(total_dur, target_end), 2)
                else:
                    et = round(min(total_dur, target_end), 2)
            else:
                et = round(min(total_dur, target_end), 2)

            acc = et
            screen_text = "\n".join(lines)

            matched_img_url = ""
            if SESSION["cached_images"] and SESSION["image_embeddings"] is not None:
                if len(used_images) >= len(SESSION["cached_images"]):
                    used_images.clear()
                fallback = SESSION["cached_images"][idx % len(SESSION["cached_images"])]
                best = video_engine.find_best_image_by_clip(
                    caption_text=screen_text,
                    valid_paths=SESSION["cached_images"],
                    image_embeddings=SESSION["image_embeddings"],
                    fallback_file=fallback,
                    used_paths=used_images
                )
                used_images.add(best)
                matched_img_url = f"/api/get_image/{best.name}"

            rows.append({
                "index": idx,
                "caption": screen_text,
                "lines": lines,
                "start_time": st,
                "end_time": et,
                "duration": round(et - st, 2),
                "matched_img": matched_img_url
            })

        SESSION["rows"] = rows
        set_progress("Alignment complete!", 100)
        return {
            "success": True,
            "total": len(rows),
            "rows": rows,
            "audio_url": "/api/stream_audio",
            "has_logo": bool(SESSION["logo_path"])
        }
    except Exception as e:
        set_progress(f"Error: {str(e)}", 0)
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.post("/api/shift_all_timestamps")
async def shift_all_timestamps(payload: Dict[str, Any]):
    offset = float(payload.get("offset_sec", 0.0))
    for r in SESSION["rows"]:
        if r["index"] == 0:
            r["end_time"] = round(max(1.0, r["end_time"] + offset), 2)
            r["duration"] = r["end_time"]
        else:
            r["start_time"] = round(max(0.0, r["start_time"] + offset), 2)
            r["end_time"] = round(max(r["start_time"] + 0.5, r["end_time"] + offset), 2)
            r["duration"] = round(r["end_time"] - r["start_time"], 2)
    return {"success": True, "rows": SESSION["rows"]}


@app.post("/api/insert_row")
async def insert_row(payload: Dict[str, Any]):
    after_idx = int(payload.get("after_index", -1))
    if 0 <= after_idx < len(SESSION["rows"]):
        prev_row = SESSION["rows"][after_idx]
        st = prev_row["end_time"]

        if after_idx + 1 < len(SESSION["rows"]):
            next_row = SESSION["rows"][after_idx + 1]
            mid = round((st + next_row["start_time"]) / 2.0, 2)
            et = next_row["start_time"] if mid <= st else mid
        else:
            et = round(st + 5.0, 2)

        new_segment = {
            "index": after_idx + 1,
            "caption": "စာသား အသစ် ရိုက်ထည့်ရန်...",
            "lines": ["စာသား အသစ် ရိုက်ထည့်ရန်..."],
            "start_time": st,
            "end_time": et,
            "duration": round(et - st, 2),
            "matched_img": prev_row.get("matched_img", "")
        }

        SESSION["rows"].insert(after_idx + 1, new_segment)
        for i, r in enumerate(SESSION["rows"]):
            r["index"] = i
        return {"success": True, "rows": SESSION["rows"], "inserted_index": after_idx + 1}
    return {"success": False, "error": "Invalid index"}


@app.post("/api/delete_row")
async def delete_row(payload: Dict[str, Any]):
    idx = int(payload.get("index", -1))
    if 0 <= idx < len(SESSION["rows"]):
        SESSION["rows"].pop(idx)
        for i, r in enumerate(SESSION["rows"]):
            r["index"] = i
        return {"success": True, "rows": SESSION["rows"]}
    return {"success": False, "error": "Invalid index"}


@app.get("/api/get_image/{filename}")
async def get_image(filename: str):
    f_path = Path(SESSION["media_dir"]) / filename
    if f_path.exists():
        return FileResponse(f_path)
    return JSONResponse({"error": "Image not found"}, status_code=404)


@app.get("/api/stream_audio")
async def stream_audio():
    if os.path.exists(SESSION["audio_path"]):
        return FileResponse(SESSION["audio_path"], media_type="audio/mpeg")
    return JSONResponse({"error": "No audio loaded"}, status_code=404)


@app.get("/api/get_logo")
async def get_logo():
    if SESSION["logo_path"] and os.path.exists(SESSION["logo_path"]):
        return FileResponse(SESSION["logo_path"])
    return JSONResponse({"error": "No logo"}, status_code=404)


@app.post("/api/update_row")
async def update_row(payload: Dict[str, Any]):
    idx = int(payload.get("index", 0))
    if 0 <= idx < len(SESSION["rows"]):
        SESSION["rows"][idx]["caption"] = payload.get("caption", "")
        SESSION["rows"][idx]["start_time"] = float(payload.get("start_time", 0.0))
        SESSION["rows"][idx]["end_time"] = float(payload.get("end_time", 0.0))
        SESSION["rows"][idx]["duration"] = round(
            SESSION["rows"][idx]["end_time"] - SESSION["rows"][idx]["start_time"], 2
        )
        return {"success": True, "row": SESSION["rows"][idx]}
    return {"success": False}


@app.post("/api/start_render")
async def start_render(
    background_tasks: BackgroundTasks,
    format: str = Form("landscape"),
    font_size: int = Form(48),
    line_spacing: int = Form(26),
    opacity: int = Form(45),
    enable_bgm: bool = Form(True)
):
    if not SESSION["rows"] or not SESSION["audio_path"] or not SESSION["media_dir"]:
        return JSONResponse({"success": False, "error": "Missing assets or image folder."}, status_code=400)

    SESSION["is_rendering"] = True
    set_progress("Initializing render...", 2)

    def _render_task():
        df = pd.DataFrame(SESSION["rows"])
        downloads_dir = get_user_downloads_dir()
        downloads_dir.mkdir(parents=True, exist_ok=True)
        out_file = downloads_dir / "final_dhamma_video.mp4"

        cfg = {
            "format": format,
            "font_size": font_size,
            "line_spacing": line_spacing,
            "opacity": opacity,
            "enable_bgm": enable_bgm
        }

        success, res = video_engine.render_all_clips(
            df=df,
            media_dir=SESSION["media_dir"],
            audio_path=SESSION["audio_path"],
            output_file=str(out_file),
            logo_path=SESSION["logo_path"],
            cfg=cfg,
            progress_cb=set_progress
        )
        SESSION["is_rendering"] = False
        if success:
            SESSION["last_video"] = str(out_file)

    background_tasks.add_task(_render_task)
    return {"success": True}


@app.get("/api/download_video")
async def download_video():
    if SESSION["last_video"] and os.path.exists(SESSION["last_video"]):
        return FileResponse(SESSION["last_video"], media_type="video/mp4", filename="final_dhamma_video.mp4")
    return JSONResponse({"error": "Video not ready."}, status_code=404)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)