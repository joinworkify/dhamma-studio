import os
import re
import html
import shutil
import platform
import subprocess
import tempfile
from pathlib import Path
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from sentence_transformers import SentenceTransformer, util
import torch

BASE_DIR = Path(__file__).resolve().parent
CURRENT_OS = platform.system().lower()

CACHE_DIR = BASE_DIR / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

_CLIP_MODEL = None


def get_clip_model():
    global _CLIP_MODEL
    if _CLIP_MODEL is None:
        _CLIP_MODEL = SentenceTransformer("clip-ViT-B-32")
    return _CLIP_MODEL


def _resolve_ffmpeg():
    exe_name = "ffmpeg.exe" if CURRENT_OS == "windows" else "ffmpeg"
    bundled = BASE_DIR / "ffmpeg-bin" / exe_name
    if bundled.exists():
        return str(bundled)
    found = shutil.which("ffmpeg")
    return found if found else "ffmpeg"


FFMPEG_BIN = _resolve_ffmpeg()


def resolve_font_path(target_lang: str = "my"):
    """
    ရွေးချယ်ထားသော Language အလိုက် သင့်လျော်သော Font ဖိုင်ကို တိကျစွာ ရှာဖွေပေးခြင်း
    """
    lang = (target_lang or "my").lower().strip()

    # 1. ဂျပန် (Japanese)
    if "ja" in lang or "japan" in lang:
        for p in [
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf"),
            Path("/usr/share/fonts/truetype/takao-gothic/TakaoPGothic.ttf"),
            BASE_DIR / "fonts" / "NotoSansJP-Regular.ttf",
            Path("C:/Windows/Fonts/msgothic.ttc"),
        ]:
            if p.exists(): return str(p.resolve())

    # 2. တရုတ် (Chinese)
    elif "zh" in lang or "cn" in lang or "tw" in lang:
        for p in [
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
            BASE_DIR / "fonts" / "NotoSansSC-Regular.ttf",
            Path("C:/Windows/Fonts/msyh.ttc"),
        ]:
            if p.exists(): return str(p.resolve())

    # 3. ကိုရီးယား (Korean)
    elif "ko" in lang or "korean" in lang:
        for p in [
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
            BASE_DIR / "fonts" / "NotoSansKR-Regular.ttf",
            Path("C:/Windows/Fonts/malgun.ttf"),
        ]:
            if p.exists(): return str(p.resolve())

    # 4. ထိုင်း (Thai)
    elif "th" in lang or "thai" in lang:
        for p in [
            Path("/usr/share/fonts/truetype/noto/NotoSansThai-Regular.ttf"),
            Path("/usr/share/fonts/truetype/thai/Loma.ttf"),
            Path("/usr/share/fonts/truetype/tlwg/Loma.ttf"),
            BASE_DIR / "fonts" / "NotoSansThai-Regular.ttf",
            Path("C:/Windows/Fonts/leelawad.ttf"),
        ]:
            if p.exists(): return str(p.resolve())

    # 5. လက်တင် အက္ခရာသုံး ဘာသာများ (English, Vietnamese, Spanish, Tagalog, French, German)
    elif lang in ["en", "vi", "es", "tl", "fr", "de"]:
        for p in [
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"),
            Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
            Path("C:/Windows/Fonts/arial.ttf"),
        ]:
            if p.exists(): return str(p.resolve())

    # 6. မြန်မာစာနှင့် ပါဠိတော် (Myanmar / Pali Default)
    for p in [
        BASE_DIR / "fonts" / "NamKhone Grand (2).ttf",
        BASE_DIR / "fonts" / "NamKhone Grand.ttf",
        BASE_DIR / "fonts" / "NamKhoneGrand.ttf",
        BASE_DIR / "NamKhone Grand.ttf",
        Path("/usr/share/fonts/truetype/noto/NotoSansMyanmar-Bold.ttf"),
        Path("/usr/share/fonts/truetype/noto/NotoSansMyanmar-Regular.ttf"),
        Path("C:/Windows/Fonts/mmrtextb.ttf"),
        Path("C:/Windows/Fonts/mmrtext.ttf"),
    ]:
        if p.exists(): return str(p.resolve())

    # Fallback any available system font
    for p in [
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    ]:
        if p.exists(): return str(p.resolve())

    return ""


def resolve_bgm_path():
    candidates = [
        BASE_DIR / "assets" / "dhamma_bgm.mp3",
        BASE_DIR / "assets" / "dhamma_bgm.mp3.mp3",
        BASE_DIR / "dhamma_bgm.mp3",
    ]
    for c in candidates:
        if c.exists():
            return str(c.resolve())
    return ""


def scan_and_index_images(media_files, progress_cb=None):
    cache_file = CACHE_DIR / "clip_embeddings_cache.pt"
    current_valid_paths = sorted(
        [p for p in media_files if p.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]],
        key=lambda x: x.name.lower()
    )
    if not current_valid_paths:
        return [], None

    cached_dict = {}
    if cache_file.exists():
        try:
            cached_dict = torch.load(cache_file, weights_only=False)
            if not isinstance(cached_dict, dict):
                cached_dict = {}
        except Exception:
            cached_dict = {}

    new_paths = [p for p in current_valid_paths if str(p.resolve()) not in cached_dict]

    if new_paths:
        if progress_cb:
            progress_cb(f"AI scanning {len(new_paths)} media files...", 25)
        model = get_clip_model()
        new_images = []
        processable = []
        for p in new_paths:
            try:
                img = Image.open(p).convert("RGB")
                img.thumbnail((320, 320), Image.Resampling.BILINEAR)
                new_images.append(img)
                processable.append(p)
            except Exception:
                continue

        if new_images:
            with torch.no_grad():
                new_embeddings = model.encode(new_images, batch_size=32, convert_to_tensor=True, show_progress_bar=False)
            for p, emb in zip(processable, new_embeddings):
                cached_dict[str(p.resolve())] = emb.cpu()
            try:
                torch.save(cached_dict, cache_file)
            except Exception:
                pass

    final_paths, final_embeddings_list = [], []
    for p in current_valid_paths:
        k = str(p.resolve())
        if k in cached_dict:
            final_paths.append(p)
            final_embeddings_list.append(cached_dict[k])

    if not final_embeddings_list:
        return final_paths, None
    return final_paths, torch.stack(final_embeddings_list)


def batch_match_images_hybrid(clip_queries, valid_paths, image_embeddings, top_k=5, penalty_weight=0.35):
    if not valid_paths:
        return [Path() for _ in clip_queries]
    if image_embeddings is None:
        return [valid_paths[i % len(valid_paths)] for i in range(len(clip_queries))]

    model = get_clip_model()
    clean_queries = [str(q).strip() or "dhamma temple monks nature" for q in clip_queries]
    with torch.no_grad():
        text_embeddings = model.encode(clean_queries, batch_size=32, convert_to_tensor=True)
        cos_matrix = util.cos_sim(text_embeddings, image_embeddings)

    matched_results = []
    usage_counts = Counter()
    total_imgs = len(valid_paths)

    for row in cos_matrix:
        scores = row.tolist()
        unused = [i for i in range(total_imgs) if usage_counts[i] == 0]
        candidates = unused if unused else list(range(total_imgs))

        best_idx = max(candidates, key=lambda i: scores[i] - (usage_counts[i] * max(penalty_weight, 0.35)))
        usage_counts[best_idx] += 1
        matched_results.append(valid_paths[best_idx])

    return matched_results


def parse_html_tokens(html_content: str):
    raw = html.unescape(str(html_content or "")).strip()
    raw = re.sub(r'<div><br\s*/?></div>', '\n', raw, flags=re.I)
    raw = re.sub(r'<div>', '\n', raw, flags=re.I)
    raw = re.sub(r'</div>', '', raw, flags=re.I)
    raw = re.sub(r'<br\s*/?>', '\n', raw, flags=re.I)
    raw = re.sub(r'<p\s*[^>]*>', '\n', raw, flags=re.I)
    raw = re.sub(r'</p>', '', raw, flags=re.I)

    raw_lines = raw.split("\n")
    parsed_lines = []

    for l in raw_lines:
        l_str = l.strip()
        if not l_str:
            continue

        is_box = ("data-style=\"box\"" in l_str) or ("data-bg=" in l_str) or ("background-color:" in l_str)
        if is_box:
            bg_m = re.search(r'data-bg=["\']([^"\']+)["\']', l_str)
            if not bg_m:
                bg_m = re.search(r'background-color:\s*([^;"]+)', l_str)
            bc_m = re.search(r'data-bc=["\']([^"\']+)["\']', l_str)
            if not bc_m:
                bc_m = re.search(r'border(?:\-color)?:\s*(?:2px\s+solid\s+)?([^;"]+)', l_str)

            bg = bg_m.group(1).strip() if bg_m else "#8c4e12"
            bc = bc_m.group(1).strip() if bc_m else "#ffffff"
            clean_txt = re.sub(r'<[^>]+>', '', l_str).strip()
            if clean_txt:
                parsed_lines.append({"text": clean_txt, "style": "box", "bg": bg, "bc": bc})
                continue

        is_outline = ("data-style=\"outline\"" in l_str) or ("data-c=" in l_str)
        if is_outline:
            c_m = re.search(r'data-c=["\']([^"\']+)["\']', l_str)
            c = c_m.group(1).strip() if c_m else "#000000"
            clean_txt = re.sub(r'<[^>]+>', '', l_str).strip()
            if clean_txt:
                parsed_lines.append({"text": clean_txt, "style": "outline", "outline_color": c})
                continue

        clean_txt = re.sub(r'<[^>]+>', '', l_str).strip()
        if clean_txt:
            parsed_lines.append({"text": clean_txt, "style": "normal"})

    return parsed_lines


def wrap_caption_items(parsed_lines, draw, font, max_width):
    """Wrap caption lines to the same usable width as the browser preview.
    Supports both space-separated languages and scripts without spaces.
    """
    wrapped = []

    def text_width(value):
        if not value:
            return 0
        box = draw.textbbox((0, 0), value, font=font)
        return box[2] - box[0]

    def split_piece(piece):
        piece = str(piece or "").strip()
        if not piece:
            return []
        if text_width(piece) <= max_width:
            return [piece]

        # Prefer word wrapping for Latin/space-separated text.
        words = piece.split()
        if len(words) > 1:
            lines = []
            current = ""
            for word in words:
                candidate = word if not current else current + " " + word
                if text_width(candidate) <= max_width:
                    current = candidate
                else:
                    if current:
                        lines.append(current)
                    # A single very long word still needs character wrapping.
                    if text_width(word) > max_width:
                        chunk = ""
                        for ch in word:
                            test = chunk + ch
                            if chunk and text_width(test) > max_width:
                                lines.append(chunk)
                                chunk = ch
                            else:
                                chunk = test
                        current = chunk
                    else:
                        current = word
            if current:
                lines.append(current)
            return lines

        # Character wrapping for Burmese, CJK, Thai and long unspaced text.
        lines = []
        current = ""
        for ch in piece:
            candidate = current + ch
            if current and text_width(candidate) > max_width:
                lines.append(current)
                current = ch
            else:
                current = candidate
        if current:
            lines.append(current)
        return lines

    for item in parsed_lines:
        original = str(item.get("text", ""))
        for explicit_line in original.splitlines() or [original]:
            parts = split_piece(explicit_line)
            for part in parts:
                new_item = dict(item)
                new_item["text"] = part
                wrapped.append(new_item)
    return wrapped


def build_final_segment_frame(bg_path, width, height, parsed_lines, font_path, font_size, line_spacing, opacity_pct, logo_path, is_mobile=False):
    try:
        orig = Image.open(bg_path).convert("RGB")
        if is_mobile:
            scale = max(width / orig.width, height / orig.height)
            bg_w, bg_h = int(orig.width * scale), int(orig.height * scale)
            bg = orig.resize((bg_w, bg_h), Image.Resampling.BILINEAR)
            cx, cy = (bg_w - width) // 2, (bg_h - height) // 2
            base_canvas = bg.crop((cx, cy, cx + width, cy + height)).filter(ImageFilter.BoxBlur(radius=18))
            
            fg_w = width
            fg_h = min(int(height * 0.52), int(orig.height * (width / orig.width)))
            fg = orig.resize((fg_w, fg_h), Image.Resampling.BILINEAR)
            base_canvas.paste(fg, (0, (height - fg_h) // 2))
        else:
            scale = max(width / orig.width, height / orig.height)
            new_w, new_h = int(orig.width * scale), int(orig.height * scale)
            resized = orig.resize((new_w, new_h), Image.Resampling.BILINEAR)
            cx, cy = (new_w - width) // 2, (new_h - height) // 2
            base_canvas = resized.crop((cx, cy, cx + width, cy + height))
    except Exception:
        base_canvas = Image.new("RGB", (width, height), (20, 20, 25))

    frame = base_canvas.convert("RGBA")
    dimmer = Image.new("RGBA", (width, height), (0, 0, 0, int(255 * (opacity_pct / 100.0))))
    frame = Image.alpha_composite(frame, dimmer)

    if logo_path and os.path.exists(logo_path):
        try:
            logo_img = Image.open(logo_path).convert("RGBA")
            logo_size = int(height * 0.08)
            logo_img.thumbnail((logo_size, logo_size), Image.Resampling.BILINEAR)
            pos_x = width - logo_img.width - (35 if is_mobile else 40)
            pos_y = 35 if is_mobile else 30
            frame.paste(logo_img, (pos_x, pos_y), logo_img)
        except Exception:
            pass

    draw = ImageDraw.Draw(frame)
    try:
        if font_path and os.path.exists(font_path):
            font = ImageFont.truetype(font_path, font_size, layout_engine=ImageFont.Layout.RAQM)
        else:
            font = ImageFont.load_default()
    except Exception:
        try:
            font = ImageFont.truetype(font_path, font_size)
        except Exception:
            font = ImageFont.load_default()

    # Keep the rendered text inside the same approximate width used by the preview.
    max_text_width = int(width * (0.86 if is_mobile else 0.88))
    parsed_lines = wrap_caption_items(parsed_lines, draw, font, max_text_width)

    measured = []
    total_text_height = 0
    for item in parsed_lines:
        txt = item["text"]
        bbox = draw.textbbox((0, 0), txt, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        measured.append({"item": item, "w": w, "h": h})
        total_text_height += h + line_spacing

    if total_text_height > 0:
        total_text_height -= line_spacing

    curr_y = (height - total_text_height) // 2

    for m in measured:
        item = m["item"]
        txt = item["text"]
        w = m["w"]
        h = m["h"]
        curr_x = (width - w) // 2
        style = item.get("style", "normal")

        if style == "box":
            bg_color = item.get("bg", "#8c4e12")
            bc_color = item.get("bc", "#ffffff")
            pad_x = int(font_size * 0.38)
            pad_y = int(font_size * 0.16)
            rect_box = [curr_x - pad_x, curr_y - pad_y, curr_x + w + pad_x, curr_y + h + pad_y]
            draw.rounded_rectangle(rect_box, radius=10, fill=bg_color, outline=bc_color, width=3)
            draw.text((curr_x, curr_y), txt, font=font, fill=(255, 255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0, 255))
        elif style == "outline":
            oc = item.get("outline_color", "#000000")
            draw.text((curr_x, curr_y), txt, font=font, fill=(255, 255, 255, 255), stroke_width=3, stroke_fill=oc)
        else:
            draw.text((curr_x, curr_y), txt, font=font, fill=(255, 255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0, 255))

        curr_y += h + line_spacing

    return frame.convert("RGB")


def get_resolution(format_type: str, quality: str = "720p"):
    is_mobile = (format_type == "mobile")
    if quality == "1080p":
        return (1080, 1920) if is_mobile else (1920, 1080)
    elif quality == "540p":
        return (540, 960) if is_mobile else (960, 540)
    else:
        return (720, 1280) if is_mobile else (1280, 720)


def render_all_clips(df, media_dir, audio_path, output_file, logo_path, cfg, progress_cb):
    temp_dir = Path(tempfile.mkdtemp(prefix="dhamma_opt_"))
    try:
        format_type = cfg.get("format", "landscape")
        quality = cfg.get("quality", "720p")
        is_mobile = (format_type == "mobile")
        target_lang = str(cfg.get("target_lang", "my")).lower().strip()
        
        width, height = get_resolution(format_type, quality)
        base_font_sz = int(cfg.get("font_size", 38 if is_mobile else 44))
        scale_ratio = height / (1920 if is_mobile else 1080)
        font_size = max(18, int(base_font_sz * scale_ratio))
        line_spacing = max(6, int(int(cfg.get("line_spacing", 26)) * scale_ratio))
        opacity = int(cfg.get("opacity", 45))
        
        # Target language အတွက် Font ရယူခြင်း
        font_path = resolve_font_path(target_lang=target_lang)

        search_dirs = [Path(media_dir), BASE_DIR / "uploads" / "images", BASE_DIR / "images", BASE_DIR]
        fallback_images = []
        for d in search_dirs:
            if d.exists():
                fallback_images += list(d.glob("*.jpg")) + list(d.glob("*.png"))
        default_fallback = fallback_images[0] if fallback_images else Path("empty.jpg")

        progress_cb(f"Synthesizing [{target_lang.upper()}] scenes...", 15)

        total_rows = len(df)
        concat_txt = temp_dir / "timeline_concat.txt"

        with open(concat_txt, "w", encoding="utf-8") as f_out:
            for idx, row in df.iterrows():
                m_img = row.get("matched_img", "")
                img_name = Path(m_img).name if m_img else ""
                
                source_p = None
                for d in search_dirs:
                    if (d / img_name).exists():
                        source_p = d / img_name
                        break
                if not source_p:
                    source_p = default_fallback

                dur = max(0.4, float(row["end_time"]) - float(row["start_time"]))
                
                # Always render the caption currently held by the preview.
                # This preserves manual edits, deleted punctuation and line breaks.
                caption_text = str(row.get("caption", ""))

                parsed_tokens = parse_html_tokens(caption_text)
                
                frame_img = build_final_segment_frame(
                    source_p, width, height, parsed_tokens, font_path, font_size,
                    line_spacing, opacity, logo_path, is_mobile=is_mobile
                )
                
                seg_file = temp_dir / f"seg_{idx}.jpg"
                frame_img.save(seg_file, "JPEG", quality=92)

                f_out.write(f"file '{str(seg_file.resolve()).replace(chr(92), '/')}'\n")
                f_out.write(f"duration {dur:.3f}\n")

                if idx % 3 == 0 or idx == total_rows - 1:
                    pct = 15 + int((idx / max(1, total_rows)) * 30)
                    progress_cb(f"Synthesized {idx+1}/{total_rows} scenes ({target_lang.upper()})...", pct)

            if total_rows > 0:
                last_seg = temp_dir / f"seg_{total_rows - 1}.jpg"
                f_out.write(f"file '{str(last_seg.resolve()).replace(chr(92), '/')}'\n")

        total_duration = max(1.0, float(df["end_time"].max()) if len(df) else 1.0)
        first_clip_duration = max(0.5, float(df.iloc[0]["end_time"])) if len(df) else total_duration

        enable_bgm_cfg = bool(cfg.get("enable_bgm", True))
        bgm_path = resolve_bgm_path()
        has_intro_bgm = (enable_bgm_cfg and bgm_path and os.path.exists(bgm_path))

        input_args = [
            "-f", "concat", "-safe", "0", "-i", str(concat_txt),
            "-i", str(audio_path)
        ]

        if has_intro_bgm:
            input_args += ["-i", str(bgm_path)]
            fade_dur = min(1.5, first_clip_duration * 0.3)
            fade_start = max(0.0, first_clip_duration - fade_dur)
            filter_complex_str = (
                f"[2:a]atrim=0:{first_clip_duration:.2f},volume=0.20,"
                f"afade=t=out:st={fade_start:.2f}:d={fade_dur:.2f}[bgm_intro];"
                f"[1:a][bgm_intro]amix=inputs=2:duration=first:dropout_transition=0[a_out]"
            )
            audio_map = "[a_out]"
        else:
            filter_complex_str = ""
            audio_map = "1:a"

        cmd = [
            FFMPEG_BIN, "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
            *input_args
        ]

        if filter_complex_str:
            cmd += ["-filter_complex", filter_complex_str]

        cmd += [
            "-map", "0:v",
            "-map", audio_map,
            "-t", f"{total_duration:.3f}",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "22",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k",
            "-progress", "pipe:1",
            "-nostats",
            str(output_file)
        ]

        progress_cb(f"Encoding [{target_lang.upper()}] video...", 50)
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)

        for line in process.stdout:
            line = line.strip()
            if line.startswith("out_time_us="):
                try:
                    val = int(line.split("=", 1)[1])
                    elapsed = val / 1_000_000
                    pct = min(99, 50 + int((elapsed / total_duration) * 48))
                    progress_cb(f"Rendering {target_lang.upper()} ({int((elapsed/total_duration)*100)}%)...", pct)
                except Exception:
                    pass

        process.wait(timeout=300)
        if process.returncode != 0:
            err = process.stderr.read()
            return False, f"FFmpeg Error: {err}"

        progress_cb(f"[{target_lang.upper()}] Video ready! Click Download.", 100)
        return True, str(output_file)
    except Exception as e:
        return False, str(e)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)