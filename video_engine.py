import html
import os
import platform
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
import mutagen
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from sentence_transformers import SentenceTransformer, util
import torch

BASE_DIR = Path(__file__).resolve().parent
CURRENT_OS = platform.system().lower()

# ============================================================
# AI VISION / CLIP SEMANTIC MATCHER (LIGHTWEIGHT & FAST)
# ============================================================

_CLIP_MODEL = None

def get_clip_model():
    global _CLIP_MODEL
    if _CLIP_MODEL is None:
        _CLIP_MODEL = SentenceTransformer("clip-ViT-B-32")
    return _CLIP_MODEL


def scan_and_index_images(media_dir, media_files, progress_cb=None):
    cache_file = Path(media_dir) / ".clip_embeddings_cache.pt"
    
    current_valid_paths = [
        p for p in media_files 
        if p.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]
    ]

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
            progress_cb(f"AI scanning {len(new_paths)} new image(s)...", 7)

        model = get_clip_model()
        new_images = []
        processable_paths = []

        for p in new_paths:
            try:
                img = Image.open(p).convert("RGB")
                img.thumbnail((384, 384), Image.Resampling.BILINEAR)
                new_images.append(img)
                processable_paths.append(p)
            except Exception:
                continue

        if new_images:
            with torch.no_grad():
                new_embeddings = model.encode(
                    new_images,
                    batch_size=32,
                    convert_to_tensor=True,
                    show_progress_bar=False,
                )

            for p, emb in zip(processable_paths, new_embeddings):
                cached_dict[str(p.resolve())] = emb.cpu()

            try:
                torch.save(cached_dict, cache_file)
            except Exception:
                pass
    else:
        if progress_cb:
            progress_cb("All images matched from cache instantly!", 10)

    final_paths = []
    final_embeddings_list = []

    for p in current_valid_paths:
        p_str = str(p.resolve())
        if p_str in cached_dict:
            final_paths.append(p)
            final_embeddings_list.append(cached_dict[p_str])

    if not final_embeddings_list:
        return final_paths, None

    all_embeddings = torch.stack(final_embeddings_list)
    return final_paths, all_embeddings


def find_best_image_by_clip(caption_text, valid_paths, image_embeddings, fallback_file, used_paths=None):
    if image_embeddings is None or len(valid_paths) == 0:
        return fallback_file

    clean_text = clean_html_text(caption_text).strip()
    if not clean_text:
        return fallback_file

    if used_paths is None:
        used_paths = set()

    try:
        model = get_clip_model()
        with torch.no_grad():
            text_embedding = model.encode(clean_text, convert_to_tensor=True)
            cos_scores = util.cos_sim(text_embedding, image_embeddings)[0]
            sorted_indices = torch.argsort(cos_scores, descending=True).tolist()

            for idx in sorted_indices:
                candidate = valid_paths[idx]
                if candidate not in used_paths:
                    return candidate

            return valid_paths[sorted_indices[0]]
    except Exception:
        return fallback_file


# ============================================================
# TEXT / CAPTION HELPERS
# ============================================================

def hex_to_rgba(hex_code, opacity_pct):
    hex_code = str(hex_code).lstrip("#")
    if len(hex_code) == 6:
        r, g, b = tuple(int(hex_code[i:i + 2], 16) for i in (0, 2, 4))
    else:
        r, g, b = 0, 0, 0
    a = int(255 * (float(opacity_pct) / 100.0))
    return (r, g, b, a)


def get_render_font(size):
    font_candidates = [
        BASE_DIR / "fonts" / "NamKhone Grand (2).ttf",
        BASE_DIR / "fonts" / "NamKhone Grand.ttf",
        BASE_DIR / "NamKhone Grand.ttf",
        Path("/System/Library/Fonts/Supplemental/NotoSansMyanmar.ttc"),
        Path("/System/Library/Fonts/Supplemental/NotoSerifMyanmar.ttc"),
        Path("/Library/Fonts/NotoSansMyanmar-Regular.ttf"),
        Path("/usr/share/fonts/truetype/noto/NotoSansMyanmar-Bold.ttf"),
        Path("/usr/share/fonts/truetype/noto/NotoSansMyanmar-Regular.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansMyanmar-Bold.otf"),
        Path("C:/Windows/Fonts/mmrtext.ttf"),
        Path("C:/Windows/Fonts/mmrtextb.ttf"),
        Path("C:/Windows/Fonts/NotoSansMyanmar-Regular.ttf"),
    ]

    for c in font_candidates:
        c_path = Path(c)
        if c_path.exists():
            try:
                return ImageFont.truetype(str(c_path), size, layout_engine=ImageFont.Layout.RAQM)
            except Exception:
                try:
                    return ImageFont.truetype(str(c_path), size)
                except Exception:
                    pass
    return ImageFont.load_default()


def clean_html_text(text_str):
    if not text_str:
        return ""
    no_tags = re.sub(r"<[^>]+>", "", text_str)
    unescaped = html.unescape(no_tags)
    return unescaped.replace("\u00a0", " ").strip()


def parse_styled_blocks(raw_text):
    if not raw_text:
        return []

    text_str = str(raw_text).strip()
    blocks = []
    raw_lines = re.split(r"</?(?:div|p|br)[^>]*>", text_str)

    span_regex = re.compile(
        r"<span([^>]*)>(.*?)</span>",
        re.IGNORECASE | re.DOTALL
    )
    attr_regex = re.compile(r'([a-zA-Z0-9_-]+)="([^"]*)"')

    for line in raw_lines:
        line_clean = line.strip()
        if not line_clean:
            continue

        match = span_regex.search(line_clean)
        if match:
            attr_str, inner_content = match.groups()
            attrs = dict(attr_regex.findall(attr_str))

            style_type = attrs.get("data-style", "normal")
            content = clean_html_text(inner_content)
            if not content:
                continue

            if style_type == "box":
                blocks.append({
                    "text": content,
                    "is_box": True,
                    "box_bg": attrs.get("data-bg", "#8c4e12"),
                    "box_op": 90,
                    "box_bc": attrs.get("data-bc", "#ffffff"),
                    "box_bw": 4,
                    "stroke_w": 2,
                    "stroke_c": "#000000",
                })
            elif style_type == "outline":
                w = int(attrs.get("data-w", 3))
                c = attrs.get("data-c", "#000000")
                blocks.append({
                    "text": content,
                    "is_box": False,
                    "stroke_w": w,
                    "stroke_c": c,
                })
            else:
                blocks.append({
                    "text": content,
                    "is_box": False,
                    "stroke_w": 3,
                    "stroke_c": "#000000",
                })
        else:
            plain = clean_html_text(line_clean)
            if plain:
                blocks.append({
                    "text": plain,
                    "is_box": False,
                    "stroke_w": 3,
                    "stroke_c": "#000000",
                })

    return blocks


def break_lines_by_natural_delimiters(text, max_pixel_w, font):
    dummy_img = Image.new("RGBA", (1, 1))
    draw = ImageDraw.Draw(dummy_img)

    raw_tokens = re.split(r"([၊။\s])", text.strip())
    tokens = []
    i = 0

    while i < len(raw_tokens):
        tok = raw_tokens[i]
        if i + 1 < len(raw_tokens) and raw_tokens[i + 1] in ["၊", "။", " "]:
            tokens.append(tok + raw_tokens[i + 1])
            i += 2
        else:
            if tok:
                tokens.append(tok)
            i += 1

    lines = []
    curr = ""

    for tok in tokens:
        if not tok:
            continue

        test = (curr + tok) if curr else tok
        bbox = draw.textbbox((0, 0), test, font=font)
        w = bbox[2] - bbox[0]

        if w <= max_pixel_w:
            curr = test
        else:
            if curr:
                lines.append(curr.strip())
            curr = tok

    if curr:
        lines.append(curr.strip())

    return [line for line in lines if line]


# ============================================================
# LINE CHUNKING & INTRO ISOLATION
# ============================================================

def build_clip_chunks(df, width, font_size, max_lines, get_audio_path_fn, isolate_first_row=False):
    """
    isolate_first_row == True (BGM ပါရှိလျှင်) -> Row 0 (ခေါင်းစဉ်) ကို သီးသန့် ခွဲထုတ်ထားမည်။
    ကျန်ရှိသော အပိုင်းများကို max_lines စီ အတိအကျ စုစည်းပေးမည်။
    """
    font = get_render_font(font_size)
    max_pixel_w = int(width * 0.76)
    
    stream_units = []
    intro_chunk = None

    for row_idx, (_, row) in enumerate(df.iterrows()):
        cap = str(row["caption"]).strip() if str(row["caption"]) != "nan" else ""
        mp3 = str(row["mp3"]).strip()
        audio_path = get_audio_path_fn(mp3)

        if not audio_path or not os.path.exists(audio_path):
            continue

        try:
            dur = max(float(mutagen.File(audio_path).info.length), 0.5)
        except Exception:
            dur = 3.0

        blocks = parse_styled_blocks(cap)
        extracted_lines = []
        for b in blocks:
            lines = break_lines_by_natural_delimiters(b["text"], max_pixel_w, font)
            for l_txt in lines:
                extracted_lines.append((l_txt, b))

        if not extracted_lines:
            continue

        total_chars = sum(len(txt) for txt, _ in extracted_lines) or 1
        acc_start = 0.0
        row_units = []

        for l_idx, (txt, b_meta) in enumerate(extracted_lines):
            l_dur = (len(txt) / total_chars) * dur
            start_sec = acc_start
            end_sec = dur if l_idx == len(extracted_lines) - 1 else round(acc_start + l_dur, 3)
            acc_start = end_sec

            unit = {
                "text": txt,
                "block_meta": b_meta,
                "audio_path": audio_path,
                "start_sec": start_sec,
                "end_sec": end_sec,
                "duration": max(0.2, end_sec - start_sec),
                "row_idx": row_idx,
            }
            row_units.append(unit)

        # ပထမဆုံး Row (ခေါင်းစဉ်) ကို သီးသန့် Intro အနေဖြင့် ထားခြင်း
        if isolate_first_row and intro_chunk is None:
            intro_chunk = row_units
        else:
            stream_units.extend(row_units)

    chunks = []
    if intro_chunk:
        chunks.append(intro_chunk)

    # ကျန် stream များကို max_lines (ဥပမာ ၃ လိုင်း) အပြည့် ဖွဲ့စည်းခြင်း
    for i in range(0, len(stream_units), max_lines):
        chunks.append(stream_units[i:i + max_lines])

    return chunks


# ============================================================
# IMAGE LAYERS
# ============================================================

def create_static_dimmer_overlay(
    width,
    height,
    is_mobile,
    output_path,
    logo_path="",
    overlay_mode="Full Video Overlay",
    rgba_color=(0, 0, 0, 115),
):
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    if overlay_mode == "Full Video Overlay" and rgba_color[3] > 0:
        draw.rectangle([0, 0, width, height], fill=rgba_color)

    if logo_path and os.path.exists(logo_path):
        try:
            logo_img = Image.open(logo_path).convert("RGBA")
            logo_size = int(110 if is_mobile else 140)
            logo_img.thumbnail((logo_size, logo_size), Image.Resampling.LANCZOS)

            margin = 60 if not is_mobile else 75
            pos_x = width - logo_img.width - margin
            pos_y = margin

            overlay.paste(logo_img, (pos_x, pos_y), logo_img)
        except Exception:
            pass

    overlay.save(output_path, "PNG")


def render_blocks_to_image(
    blocks,
    width,
    height,
    font_size,
    line_spacing,
    pos_choice,
    is_mobile,
    output_path
):
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    if not blocks:
        overlay.save(output_path, "PNG")
        return

    font_normal = get_render_font(font_size)
    font_box = get_render_font(int(font_size * 1.15))

    rendered_items = []
    total_content_h = 0

    for b in blocks:
        is_box = b.get("is_box", False)
        curr_font = font_box if is_box else font_normal
        formatted = b.get("text", "")

        bbox = draw.multiline_textbbox(
            (0, 0),
            formatted,
            font=curr_font,
            align="center",
            spacing=line_spacing
        )

        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]

        pad_x = 28 if is_box else 16
        pad_y = 18 if is_box else 10

        bw = min(int(width * 0.90), tw + (pad_x * 2)) if is_box else tw
        bh = th + (pad_y * 2) if is_box else th

        rendered_items.append({
            "formatted": formatted,
            "block_meta": b,
            "font": curr_font,
            "text_w": tw,
            "text_h": th,
            "box_w": bw,
            "box_h": bh,
            "pad_x": pad_x,
            "pad_y": pad_y,
        })

        total_content_h += bh + line_spacing

    total_content_h -= line_spacing

    if pos_choice == "high":
        start_y = 120 if not is_mobile else 220
    elif pos_choice == "low":
        start_y = height - total_content_h - (120 if not is_mobile else 280)
    else:
        start_y = (height - total_content_h) // 2

    curr_y = start_y

    for item in rendered_items:
        fmt = item["formatted"]
        font = item["font"]
        b = item["block_meta"]
        is_box = b.get("is_box", False)

        if is_box:
            bx = (width - item["box_w"]) // 2
            by = curr_y

            box_fill_rgba = hex_to_rgba(b.get("box_bg", "#8c4e12"), b.get("box_op", 90))
            box_border_rgba = hex_to_rgba(b.get("box_bc", "#ffffff"), 100)

            draw.rectangle(
                [bx, by, bx + item["box_w"], by + item["box_h"]],
                fill=box_fill_rgba,
                outline=box_border_rgba if b.get("box_bw", 4) > 0 else None,
                width=b.get("box_bw", 4),
            )

            tx = (width - item["text_w"]) // 2
            ty = by + item["pad_y"]
            curr_y += item["box_h"] + line_spacing
        else:
            tx = (width - item["text_w"]) // 2
            ty = curr_y
            curr_y += item["text_h"] + line_spacing

        s_w = b.get("stroke_w", 3)
        s_c = b.get("stroke_c", "#000000")
        s_rgba = hex_to_rgba(s_c, 100) if s_w > 0 else None

        draw.multiline_text(
            (tx, ty),
            fmt,
            font=font,
            fill=(255, 255, 255, 255),
            align="center",
            spacing=line_spacing,
            stroke_width=s_w,
            stroke_fill=s_rgba if s_w > 0 else None,
        )

    overlay.save(output_path, "PNG")


def prepare_final_image_layer(
    img_path,
    width,
    height,
    is_mobile,
    output_path
):
    try:
        orig = Image.open(img_path).convert("RGB")

        if is_mobile:
            scale_bg = max(width / orig.width, height / orig.height)
            bg_w = int(orig.width * scale_bg)
            bg_h = int(orig.height * scale_bg)

            resized_bg = orig.resize((bg_w, bg_h), Image.Resampling.BILINEAR)
            crop_x = (bg_w - width) // 2
            crop_y = (bg_h - height) // 2

            canvas = resized_bg.crop((crop_x, crop_y, crop_x + width, crop_y + height))
            canvas = canvas.filter(ImageFilter.GaussianBlur(radius=20))

            scale_fg = min(width / orig.width, height / orig.height)
            fg_w = int(orig.width * scale_fg)
            fg_h = int(orig.height * scale_fg)
            fg_img = orig.resize((fg_w, fg_h), Image.Resampling.BILINEAR)

            pos_x = (width - fg_w) // 2
            pos_y = (height - fg_h) // 2
            canvas.paste(fg_img, (pos_x, pos_y))
            canvas.save(output_path, "JPEG", quality=85)
        else:
            scale = max(width / orig.width, height / orig.height)
            new_w = int(orig.width * scale)
            new_h = int(orig.height * scale)

            resized = orig.resize((new_w, new_h), Image.Resampling.BILINEAR)
            crop_x = (new_w - width) // 2
            crop_y = (new_h - height) // 2

            canvas = resized.crop((crop_x, crop_y, crop_x + width, crop_y + height))
            canvas.save(output_path, "JPEG", quality=85)

    except Exception:
        fallback = Image.new("RGB", (width, height), (20, 20, 20))
        fallback.save(output_path, "JPEG")


# ============================================================
# CROSS-PLATFORM ENCODER DETECTION
# ============================================================

def ffmpeg_has_encoder(encoder_name):
    try:
        test_cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "nullsrc=s=64x64:d=0.05",
            "-c:v", encoder_name, "-f", "null", "-"
        ]
        result = subprocess.run(
            test_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False
        )
        return result.returncode == 0
    except Exception:
        return False


def choose_encoder(cfg):
    requested = str(cfg.get("encoder", "auto")).lower().strip()

    if requested in ("nvenc", "h264_nvenc"):
        if not ffmpeg_has_encoder("h264_nvenc"):
            raise RuntimeError("h264_nvenc is not functional or NVIDIA driver is missing.")
        return "nvenc"

    if requested in ("videotoolbox", "h264_videotoolbox"):
        if not ffmpeg_has_encoder("h264_videotoolbox"):
            raise RuntimeError("h264_videotoolbox is not functional on this system.")
        return "videotoolbox"

    if requested in ("qsv", "h264_qsv"):
        if not ffmpeg_has_encoder("h264_qsv"):
            raise RuntimeError("h264_qsv is not functional in this runtime.")
        return "qsv"

    if requested in ("x264", "libx264", "cpu"):
        return "x264"

    if CURRENT_OS == "darwin" and ffmpeg_has_encoder("h264_videotoolbox"):
        return "videotoolbox"
    elif ffmpeg_has_encoder("h264_nvenc"):
        return "nvenc"
    elif ffmpeg_has_encoder("h264_qsv"):
        return "qsv"

    return "x264"


def encoder_args(encoder):
    if encoder == "videotoolbox":
        return ["-c:v", "h264_videotoolbox", "-b:v", "4500k", "-pix_fmt", "yuv420p"]
    if encoder == "nvenc":
        return ["-c:v", "h264_nvenc", "-preset", "p1", "-rc", "vbr", "-cq", "23", "-b:v", "0", "-pix_fmt", "yuv420p"]
    if encoder == "qsv":
        return ["-c:v", "h264_qsv", "-global_quality", "23", "-pix_fmt", "nv12"]

    return ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "22", "-pix_fmt", "yuv420p"]


# ============================================================
# RENDERING
# ============================================================

def render_single_task(task):
    cmd, clip_mp4 = task

    res = subprocess.run(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )

    if res.returncode == 0:
        return clip_mp4, ""

    return None, res.stderr[-5000:]


def render_all_clips(
    df,
    media_dir,
    get_audio_path_fn,
    output_file,
    logo_path,
    cfg,
    progress_cb,
    bgm_path=""
):
    if isinstance(media_dir, (list, tuple)):
        media_dir = media_dir[0] if len(media_dir) > 0 else ""
    media_dir = str(media_dir)

    temp_dir = Path(tempfile.mkdtemp(prefix="dhamma_render_"))

    try:
        is_mobile = (cfg.get("format", "landscape") == "mobile")

        width, height = (1080, 1920) if is_mobile else (1920, 1080)
        font_size = int(cfg.get("font_size", 38 if is_mobile else 44))
        line_spacing = int(cfg.get("line_spacing", 18 if is_mobile else 22))
        pos_choice = cfg.get("position", "middle")
        max_lines = max(1, int(cfg.get("max_lines", cfg.get("lines_per_page", 3))))
        overlay_mode = cfg.get("overlay_mode", "Full Video Overlay")
        rgba_color = hex_to_rgba(cfg.get("color", "#000000"), cfg.get("opacity", 45))
        fps = max(1, int(cfg.get("fps", 12)))
        enable_bgm_cfg = bool(cfg.get("enable_bgm", True))

        encoder = choose_encoder(cfg)
        requested_workers = int(cfg.get("render_workers", 0))

        if requested_workers > 0:
            max_workers = requested_workers
        elif encoder in ("nvenc", "videotoolbox"):
            max_workers = 2 if encoder == "videotoolbox" else 1
        else:
            max_workers = min(os.cpu_count() or 2, 4)

        supported_exts = [".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mov", ".mkv", ".avi", ".webm"]
        video_exts = [".mp4", ".mov", ".mkv", ".avi", ".webm"]

        media_files = sorted(
            [
                p for p in Path(media_dir).iterdir()
                if p.is_file() and not p.name.startswith((".", "~$")) and p.suffix.lower() in supported_exts
            ]
        )

        if not media_files:
            return False, f"No image/video files found in '{media_dir}'"

        progress_cb("AI is analyzing and scanning images...", 5)
        valid_paths, image_embeddings = scan_and_index_images(media_dir, media_files, progress_cb)

        static_overlay_png = temp_dir / "static_dimmer_overlay.png"
        create_static_dimmer_overlay(
            width, height, is_mobile, str(static_overlay_png),
            logo_path=logo_path, overlay_mode=overlay_mode, rgba_color=rgba_color
        )

        # ----------------------------------------------------
        # BGM ပါရှိပါက ပထမဆုံး Row (ခေါင်းစဉ်) ကို သီးသန့် Intro အနေဖြင့် ထားခြင်း
        # ----------------------------------------------------
        has_intro_bgm = (enable_bgm_cfg and bgm_path and os.path.exists(bgm_path))
        progress_cb("Organizing title & line streams...", 10)
        
        fixed_chunks = build_clip_chunks(
            df=df,
            width=width,
            font_size=font_size,
            max_lines=max_lines,
            get_audio_path_fn=get_audio_path_fn,
            isolate_first_row=has_intro_bgm
        )

        if not fixed_chunks:
            return False, "No valid content or audio files found."

        background_cache = {}
        tasks = []
        used_images = set()
        bgm_start_offset = 10.0

        for clip_idx, chunk in enumerate(fixed_chunks):
            combined_text = "\n".join(u["text"] for u in chunk)
            clip_dur = max(0.5, sum(u["duration"] for u in chunk))

            if valid_paths and len(used_images) >= len(valid_paths):
                used_images.clear()

            fallback_choice = media_files[clip_idx % len(media_files)]
            media_path = find_best_image_by_clip(
                caption_text=combined_text,
                valid_paths=valid_paths,
                image_embeddings=image_embeddings,
                fallback_file=fallback_choice,
                used_paths=used_images
            )
            used_images.add(media_path)

            is_video_input = media_path.suffix.lower() in video_exts
            base_bg_jpg = None

            if not is_video_input:
                cache_key = (str(media_path.resolve()), width, height, is_mobile)
                if cache_key not in background_cache:
                    cached_path = temp_dir / f"bg_cache_{len(background_cache):04d}.jpg"
                    prepare_final_image_layer(media_path, width, height, is_mobile, str(cached_path))
                    background_cache[cache_key] = cached_path
                base_bg_jpg = background_cache[cache_key]

            # စာသား Overlay ဆွဲခြင်း
            text_png = temp_dir / f"chunk_{clip_idx:04d}_text.png"
            chunk_blocks = [{
                **chunk[0]["block_meta"],
                "text": combined_text,
                "_is_prewrapped": True
            }]
            render_blocks_to_image(
                chunk_blocks, width, height, font_size, line_spacing, pos_choice, is_mobile, str(text_png)
            )

            # ----------------------------------------------------
            # Audio Slices ချိတ်ဆက်ခြင်း
            # ----------------------------------------------------
            inputs = []
            if not is_video_input:
                inputs += ["-loop", "1", "-framerate", str(fps), "-i", str(base_bg_jpg)]
            else:
                inputs += ["-stream_loop", "-1", "-i", str(media_path)]

            inputs += ["-loop", "1", "-framerate", str(fps), "-i", str(static_overlay_png)]
            inputs += ["-loop", "1", "-framerate", str(fps), "-i", str(text_png)]

            audio_in_indices = []
            curr_in = 3
            for u in chunk:
                inputs += ["-i", str(u["audio_path"])]
                audio_in_indices.append((curr_in, u["start_sec"], u["end_sec"]))
                curr_in += 1

            # BGM ကို Intro Clip (clip_idx == 0) တွင်သာ သီးသန့် ထည့်သွင်းခြင်း
            include_bgm = (clip_idx == 0 and has_intro_bgm)
            bgm_idx = None
            if include_bgm:
                inputs += ["-stream_loop", "-1", "-i", str(bgm_path)]
                bgm_idx = curr_in

            # ----------------------------------------------------
            # Video & Audio Filter Graph
            # ----------------------------------------------------
            filter_parts = []
            if is_video_input:
                filter_parts.append(
                    f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},fps={fps}[base]"
                )
                last_v = "[base]"
            else:
                last_v = "[0:v]"

            filter_parts.append(f"{last_v}[1:v]overlay=0:0[bg_dim]")
            fade_dur = min(0.35, clip_dur / 2)
            filter_parts.append(f"[2:v]format=yuva420p,fade=t=in:st=0:d={fade_dur}:alpha=1[text_anim]")
            filter_parts.append(f"[bg_dim][text_anim]overlay=0:0[v]")

            # Audio segments များ trim လုပ်၍ ချိတ်ဆက်ခြင်း
            audio_concat_tags = []
            for seg_i, (in_idx, st, et) in enumerate(audio_in_indices):
                tag = f"[a_slice_{seg_i}]"
                filter_parts.append(f"[{in_idx}:a]atrim=start={st}:end={et},asetpts=PTS-STARTPTS{tag}")
                audio_concat_tags.append(tag)

            if len(audio_concat_tags) > 1:
                concat_inputs = "".join(audio_concat_tags)
                filter_parts.append(f"{concat_inputs}concat=n={len(audio_concat_tags)}:v=0:a=1[main_a]")
                speech_a = "[main_a]"
            else:
                speech_a = audio_concat_tags[0]

            if include_bgm:
                filter_parts.append(
                    f"[{bgm_idx}:a]atrim=start={bgm_start_offset},asetpts=PTS-STARTPTS,volume=0.35[bgm_a]"
                )
                filter_parts.append(
                    f"{speech_a}[bgm_a]amix=inputs=2:duration=first:dropout_transition=2[final_a]"
                )
                out_a_tag = "[final_a]"
            else:
                out_a_tag = speech_a

            filter_str = ";".join(filter_parts)
            v_encoder_args = encoder_args(encoder)
            clip_mp4 = temp_dir / f"clip_{clip_idx:04d}.mp4"

            cmd = [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error"
            ] + inputs + [
                "-filter_complex", filter_str,
                "-map", "[v]",
                "-map", out_a_tag,
                "-r", str(fps),
            ] + v_encoder_args + [
                "-c:a", "aac",
                "-b:a", "128k",
                "-t", str(clip_dur),
                "-movflags", "+faststart",
                str(clip_mp4),
            ]

            tasks.append((cmd, clip_mp4))

        if not tasks:
            return False, "No render tasks could be generated."

        progress_cb(f"Rendering with {encoder.upper()} ({max_workers} workers)...", 15)

        rendered_clips = []
        completed = 0
        first_error = ""

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(render_single_task, task) for task in tasks]

            for future in futures:
                clip_path, error_text = future.result()
                completed += 1
                progress_cb(
                    f"Rendered {completed}/{len(tasks)} clips...",
                    15 + int((completed / len(tasks)) * 75)
                )

                if clip_path:
                    rendered_clips.append(clip_path)
                elif not first_error:
                    first_error = error_text

        if not rendered_clips:
            detail = f"\n\nFFmpeg error:\n{first_error}" if first_error else ""
            return False, "Failed to render clips. Please check source assets." + detail

        progress_cb("Merging into final video...", 95)

        concat_txt = temp_dir / "concat_list.txt"
        with open(concat_txt, "w", encoding="utf-8") as f:
            for c in rendered_clips:
                safe_path = str(c.resolve()).replace("\\", "/")
                f.write(f"file '{safe_path}'\n")

        merge_cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_txt),
            "-c", "copy",
            "-movflags", "+faststart",
            str(output_file),
        ]

        res = subprocess.run(
            merge_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )

        if res.returncode != 0:
            return False, f"Error during final video concatenation:\n{res.stderr[-5000:]}"

        progress_cb("Rendering Complete!", 100)
        return True, str(output_file)

    except Exception as e:
        return False, str(e)

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)