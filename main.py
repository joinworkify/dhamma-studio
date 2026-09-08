import os
import sys
import json
import logging
from pathlib import Path
import threading
import re
import time

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
logging.getLogger("pywebview").setLevel(logging.CRITICAL)

import mutagen
import pandas as pd
import pygame
import video_engine
import webview

BASE_DIR = Path(__file__).resolve().parent

try:
    pygame.mixer.init()
except Exception:
    pass


class BackendAPI:
    def __init__(self):
        self.window = None
        self.df = None
        self.csv_path = ""
        self.audios_dir = ""
        self.images_dir = ""
        self.logo_path = ""
        self.bgm_path = ""
        self.resolve_bgm_path()
        self.output_video = str(BASE_DIR / "final_output.mp4")

        # Audio Playback & Sync State
        self.current_audio_file = ""
        self.audio_playback_start_wall = 0.0
        self.audio_paused_at_sec = 0.0
        self.audio_is_playing = False
        self.audio_is_paused = False

    def resolve_bgm_path(self):
        bgm_candidates = [
            BASE_DIR / "assets" / "dhamma_bgm.mp3",
            BASE_DIR / "assets" / "dhamma_bgm.mp3.mp3",
            BASE_DIR / "dhamma_bgm.mp3",
        ]
        self.bgm_path = ""
        for c in bgm_candidates:
            if c.exists():
                self.bgm_path = str(c.resolve())
                break

    def set_window(self, window):
        self.window = window

    def select_folder(self, dialog_type):
        result = self.window.create_file_dialog(
            webview.FileDialog.FOLDER, allow_multiple=False
        )
        if result:
            folder = result[0] if isinstance(result, (list, tuple)) else result
            folder_str = str(folder)
            if dialog_type == "images":
                self.images_dir = folder_str
            elif dialog_type == "audios":
                self.audios_dir = folder_str
            return {"success": True, "path": folder_str}
        return {"success": False, "path": ""}

    def select_file(self, file_type):
        if file_type == "csv":
            result = self.window.create_file_dialog(
                webview.FileDialog.OPEN,
                allow_multiple=False,
                file_types=("CSV Files (*.csv)", "All Files (*.*)"),
            )
            if result and len(result) > 0:
                self.csv_path = str(result[0])
                return self.load_csv_data(self.csv_path)
        elif file_type == "logo":
            result = self.window.create_file_dialog(
                webview.FileDialog.OPEN,
                allow_multiple=False,
                file_types=("Image Files (*.png;*.jpg;*.jpeg;*.webp)", "All Files (*.*)"),
            )
            if result and len(result) > 0:
                self.logo_path = str(result[0])
                return {"success": True, "path": self.logo_path}
        elif file_type == "output":
            result = self.window.create_file_dialog(
                webview.FileDialog.SAVE,
                allow_multiple=False,
                save_filename="final_output.mp4",
                file_types=("MP4 Video (*.mp4)",),
            )
            if result:
                path_str = result[0] if isinstance(result, (list, tuple)) else result
                self.output_video = str(path_str)
                return {"success": True, "path": self.output_video}
        return {"success": False}

    # ============================================================
    # OPTION A: LOAD TEXT + MP3 (NEW PROJECT)
    # ============================================================

    def load_txt_and_mp3(self):
        txt_res = self.window.create_file_dialog(
            webview.FileDialog.OPEN,
            allow_multiple=False,
            file_types=("Text Files (*.txt)", "All Files (*.*)")
        )
        if not txt_res:
            return {"success": False, "error": "Text file not selected."}
        txt_path = str(txt_res[0])

        mp3_res = self.window.create_file_dialog(
            webview.FileDialog.OPEN,
            allow_multiple=False,
            file_types=("Audio Files (*.mp3;*.wav;*.m4a)", "All Files (*.*)")
        )
        if not mp3_res:
            return {"success": False, "error": "Audio file not selected."}
        mp3_path = str(mp3_res[0])

        try:
            with open(txt_path, "r", encoding="utf-8") as f:
                content = f.read()

            raw_blocks = re.split(r"(?:(?<=[။\n])|(?=[၀-၉]+[။—]))", content)
            sentences = [re.sub(r"\s+", " ", b).strip() for b in raw_blocks if len(b.strip()) >= 3]

            if not sentences:
                return {"success": False, "error": "No valid text sentences found."}

            self.current_audio_file = mp3_path
            self.audios_dir = str(Path(mp3_path).parent)
            mp3_name = Path(mp3_path).name

            records = []
            for idx, s in enumerate(sentences):
                records.append({
                    "index": idx,
                    "caption": s,
                    "mp3": mp3_name,
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "status": "pending",
                    "duration": 0.0,
                    "char_len": len(s)
                })

            self.df = pd.DataFrame(records)[["caption", "mp3", "start_time", "end_time"]]
            self.csv_path = f"New: {Path(txt_path).name}"
            self.stop_playback()

            return {
                "success": True,
                "path": self.csv_path,
                "audios_path": self.audios_dir,
                "audio_filename": mp3_name,
                "total": len(records),
                "rows": records
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ============================================================
    # OPTION B: OPEN CLEANED CSV DIRECTLY
    # ============================================================

    def load_csv_data(self, path):
        try:
            self.df = pd.read_csv(path)
            self.df.columns = self.df.columns.str.strip().str.lower()
            if "caption" not in self.df.columns or "mp3" not in self.df.columns:
                return {
                    "success": False,
                    "error": "CSV must contain 'caption' and 'mp3' columns",
                }

            has_time = ("start_time" in self.df.columns and "end_time" in self.df.columns)
            records = []
            first_mp3_name = ""

            for idx, row in self.df.iterrows():
                cap = str(row["caption"]).strip() if str(row["caption"]) != "nan" else ""
                mp3 = str(row["mp3"]).strip()
                if not first_mp3_name and mp3:
                    first_mp3_name = mp3

                st = float(row["start_time"]) if has_time and str(row["start_time"]) != "nan" else 0.0
                et = float(row["end_time"]) if has_time and str(row["end_time"]) != "nan" else 0.0

                dur = round(max(0.0, et - st), 2)
                records.append({
                    "index": idx,
                    "caption": cap,
                    "mp3": mp3,
                    "start_time": st,
                    "end_time": et,
                    "status": "ok" if (et > st or dur > 0) else "pending",
                    "duration": dur,
                    "char_len": len(cap),
                })

            csv_dir = Path(path).parent
            if first_mp3_name:
                candidate_audio = csv_dir / first_mp3_name
                if candidate_audio.exists():
                    self.current_audio_file = str(candidate_audio.resolve())
                    self.audios_dir = str(csv_dir.resolve())
                else:
                    self.current_audio_file = self.get_audio_path(first_mp3_name)

            self.stop_playback()
            self.csv_path = path

            return {
                "success": True,
                "path": path,
                "audios_path": self.audios_dir or str(csv_dir),
                "audio_filename": first_mp3_name,
                "total": len(records),
                "rows": records,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ============================================================
    # ATTACH MP3 MANUALLY FOR CSV PROJECTS
    # ============================================================

    def select_audio_file(self):
        res = self.window.create_file_dialog(
            webview.FileDialog.OPEN,
            allow_multiple=False,
            file_types=("Audio Files (*.mp3;*.wav;*.m4a)", "All Files (*.*)")
        )
        if res and len(res) > 0:
            audio_path = str(res[0])
            self.current_audio_file = audio_path
            self.audios_dir = str(Path(audio_path).parent)
            mp3_name = Path(audio_path).name

            if self.df is not None:
                self.df["mp3"] = mp3_name

            self.stop_playback()
            return {"success": True, "audio_name": mp3_name, "audio_path": audio_path}
        return {"success": False}

    # ============================================================
    # AUDIO CONTROLLER (PLAY / PAUSE / REWIND / POSITION)
    # ============================================================

    def play_or_pause_audio(self, from_sec=None):
        if not self.current_audio_file or not os.path.exists(self.current_audio_file):
            return {"success": False, "error": "Audio file not connected. Please click 'Select MP3'."}

        try:
            if self.audio_is_playing and not self.audio_is_paused and from_sec is None:
                pygame.mixer.music.pause()
                self.audio_is_paused = True
                self.audio_paused_at_sec = max(0.0, time.time() - self.audio_playback_start_wall)
                return {"success": True, "state": "paused", "current_sec": round(self.audio_paused_at_sec, 2)}

            elif self.audio_is_paused and from_sec is None:
                pygame.mixer.music.unpause()
                self.audio_is_paused = False
                self.audio_playback_start_wall = time.time() - self.audio_paused_at_sec
                return {"success": True, "state": "playing", "current_sec": round(self.audio_paused_at_sec, 2)}

            else:
                start_point = float(from_sec) if from_sec is not None else 0.0
                pygame.mixer.music.load(self.current_audio_file)
                pygame.mixer.music.play(start=start_point)
                self.audio_playback_start_wall = time.time() - start_point
                self.audio_is_playing = True
                self.audio_is_paused = False
                return {"success": True, "state": "playing", "current_sec": round(start_point, 2)}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def seek_audio_relative(self, offset_sec):
        current_pos = self.get_current_audio_sec()
        target_pos = max(0.0, current_pos + offset_sec)
        return self.play_or_pause_audio(from_sec=target_pos)

    def get_current_audio_sec(self):
        if not self.audio_is_playing:
            return 0.0
        if self.audio_is_paused:
            return round(self.audio_paused_at_sec, 2)
        elapsed = max(0.0, time.time() - self.audio_playback_start_wall)
        return round(elapsed, 2)

    def stop_playback(self):
        try:
            pygame.mixer.music.stop()
            self.audio_is_playing = False
            self.audio_is_paused = False
            self.audio_paused_at_sec = 0.0
        except Exception:
            pass
        return {"success": True}

    def play_segment_preview(self, start_t, end_t):
        if not self.current_audio_file or not os.path.exists(self.current_audio_file):
            return {"success": False, "error": "Audio file not connected."}
        try:
            start_t = max(0.0, float(start_t))
            end_t = float(end_t)
            dur = max(0.2, end_t - start_t)

            pygame.mixer.music.load(self.current_audio_file)
            pygame.mixer.music.play(start=start_t)
            self.audio_is_playing = True
            self.audio_is_paused = False

            def _stop_timer():
                time.sleep(dur)
                pygame.mixer.music.stop()
                self.audio_is_playing = False

            threading.Thread(target=_stop_timer, daemon=True).start()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_audio_path(self, mp3_name):
        base_name = Path(mp3_name).name
        audios_folder = Path(self.audios_dir) if self.audios_dir else BASE_DIR
        candidates = [
            audios_folder / mp3_name,
            audios_folder / base_name,
            BASE_DIR / mp3_name,
            BASE_DIR / base_name,
        ]
        for c in candidates:
            if c.exists():
                return str(c.resolve())
        return ""

    def update_row_data(self, idx, mp3, caption, start_t=0.0, end_t=0.0):
        if self.df is not None and 0 <= idx < len(self.df):
            self.df.at[idx, "mp3"] = mp3
            self.df.at[idx, "caption"] = caption
            if "start_time" in self.df.columns and "end_time" in self.df.columns:
                self.df.at[idx, "start_time"] = start_t
                self.df.at[idx, "end_time"] = end_t

            dur = round(max(0.0, float(end_t) - float(start_t)), 2)
            status = "ok" if dur > 0.4 else "pending"
            return {
                "success": True,
                "status": status,
                "duration": dur,
                "char_len": len(caption),
            }
        return {"success": False}

    def export_cleaned_csv(self):
        if self.df is None:
            return {"success": False, "error": "No data to export"}
        save_path = self.window.create_file_dialog(
            webview.FileDialog.SAVE,
            save_filename="cleaned_data.csv",
            file_types=("CSV Files (*.csv)",),
        )
        if save_path:
            save_path = save_path[0] if isinstance(save_path, (list, tuple)) else save_path
            self.df.to_csv(save_path, index=False, encoding="utf-8-sig")
            return {"success": True, "path": str(save_path)}
        return {"success": False}

    def start_video_rendering(self, config):
        if not self.images_dir or self.df is None:
            return {"success": False, "error": "Images folder or CSV data is missing."}

        self.resolve_bgm_path()
        self.stop_playback()

        if isinstance(config, dict):
            config["max_lines"] = int(config.get("max_lines", config.get("lines_per_page", 3)))

        def _worker():
            def _prog(msg, pct):
                safe_msg = json.dumps(str(msg))
                self.window.evaluate_js(f"updateRenderStatus({safe_msg}, {pct})")

            try:
                def _get_audio_path(m):
                    f = Path(self.audios_dir) / m
                    if f.exists():
                        return str(f.resolve())
                    return str((BASE_DIR / m).resolve())

                success, res = video_engine.render_all_clips(
                    self.df,
                    self.images_dir,
                    _get_audio_path,
                    self.output_video,
                    self.logo_path,
                    config,
                    _prog,
                    bgm_path=self.bgm_path,
                )

                if success:
                    safe_res = json.dumps(f"Video rendered successfully:\n{res}")
                    self.window.evaluate_js(f"renderFinished(true, {safe_res})")
                else:
                    safe_err = json.dumps(f"Render Error: {res}")
                    self.window.evaluate_js(f"renderFinished(false, {safe_err})")
            except Exception as e:
                safe_err = json.dumps(f"Unexpected Error: {str(e)}")
                self.window.evaluate_js(f"renderFinished(false, {safe_err})")

        threading.Thread(target=_worker, daemon=True).start()
        return {"success": True}


if __name__ == "__main__":
    api = BackendAPI()
    html_file = (BASE_DIR / "static" / "index.html").resolve()

    window = webview.create_window(
        title="Dhamma Studio - Video Automation",
        url=html_file.as_uri(),
        js_api=api,
        width=1180,
        height=920,
        resizable=True,
    )
    api.set_window(window)

    webview.start(debug=False)