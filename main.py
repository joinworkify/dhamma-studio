import json
import os
from pathlib import Path
import threading
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
        self.output_video = str(BASE_DIR / "final_output.mp4")

    def set_window(self, window):
        self.window = window

    def select_folder(self, dialog_type):
        result = self.window.create_file_dialog(
            webview.FileDialog.FOLDER, allow_multiple=False
        )
        if result and len(result) > 0:
            folder = result[0]
            if dialog_type == "images":
                self.images_dir = folder
            elif dialog_type == "audios":
                self.audios_dir = folder
            return {"success": True, "path": folder}
        return {"success": False, "path": ""}

    def select_file(self, file_type):
        if file_type == "csv":
            result = self.window.create_file_dialog(
                webview.FileDialog.OPEN,
                allow_multiple=False,
                file_types=("CSV Files (*.csv)", "All Files (*.*)"),
            )
            if result and len(result) > 0:
                self.csv_path = result[0]
                return self.load_csv_data(self.csv_path)
        elif file_type == "output":
            result = self.window.create_file_dialog(
                webview.FileDialog.SAVE,
                allow_multiple=False,
                save_filename="final_output.mp4",
                file_types=("MP4 Video (*.mp4)",),
            )
            if result:
                # Tuple သို့မဟုတ် List ဖြစ်နေပါက ပထမ element ကို ယူပေးရန်
                path_str = result[0] if isinstance(result, (list, tuple)) else result
                self.output_video = str(path_str)
                return {"success": True, "path": self.output_video}
        return {"success": False}

    def load_csv_data(self, path):
        try:
            self.df = pd.read_csv(path)
            self.df.columns = self.df.columns.str.strip().str.lower()
            if "caption" not in self.df.columns or "mp3" not in self.df.columns:
                return {
                    "success": False,
                    "error": "CSV must contain 'caption' and 'mp3'",
                }

            records = []
            for idx, row in self.df.iterrows():
                cap = (
                    str(row["caption"]).strip()
                    if str(row["caption"]) != "nan"
                    else ""
                )
                mp3 = str(row["mp3"]).strip()
                status, dur = self.check_audio_sync(mp3, cap)
                records.append({
                    "index": idx,
                    "caption": cap,
                    "mp3": mp3,
                    "status": status,
                    "duration": dur,
                    "char_len": len(cap),
                })
            return {
                "success": True,
                "path": path,
                "total": len(records),
                "rows": records,
            }
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

    def check_audio_sync(self, mp3_name, caption):
        full_path = self.get_audio_path(mp3_name)
        if not full_path or not os.path.exists(full_path):
            return "missing", 0.0
        try:
            dur = round(mutagen.File(full_path).info.length, 2)
            c_len = len(caption)
            if dur < 1.0 and c_len > 25:
                return "too_short", dur
            elif dur > 18.0 and c_len < 10:
                return "too_long", dur
            return "ok", dur
        except Exception:
            return "ok", 0.0

    def play_audio(self, mp3_name):
        full_path = self.get_audio_path(mp3_name)
        if full_path and os.path.exists(full_path):
            pygame.mixer.music.load(full_path)
            pygame.mixer.music.play()
            return {"success": True}
        return {"success": False, "error": "Audio file not found"}

    def stop_audio(self):
        pygame.mixer.music.stop()
        return {"success": True}

    def update_row_data(self, idx, mp3, caption):
        if self.df is not None and 0 <= idx < len(self.df):
            self.df.at[idx, "mp3"] = mp3
            self.df.at[idx, "caption"] = caption
            status, dur = self.check_audio_sync(mp3, caption)
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
            return {"success": False, "error": "Images folder or CSV is missing."}

        def _worker():
            def _prog(msg, pct):
                safe_msg = json.dumps(str(msg))
                self.window.evaluate_js(f"updateRenderStatus({safe_msg}, {pct})")

            success, res = video_engine.render_all_clips(
                self.df,
                self.images_dir,
                self.get_audio_path,
                self.output_video,
                config,
                _prog,
            )

            if success:
                safe_res = json.dumps(f"Video rendered successfully:\n{res}")
                self.window.evaluate_js(f"renderFinished(true, {safe_res})")
            else:
                safe_err = json.dumps(f"Render Error: {res}")
                self.window.evaluate_js(f"renderFinished(false, {safe_err})")

        threading.Thread(target=_worker, daemon=True).start()
        return {"success": True}


if __name__ == "__main__":
    api = BackendAPI()
    html_file = (BASE_DIR / "static" / "index.html").resolve()

    window = webview.create_window(
        title="Dhamma Studio - Video Automation",
        url=f"file://{html_file}",
        js_api=api,
        width=1000,
        height=780,
        resizable=True,
    )
    api.set_window(window)

    webview.start(debug=True)