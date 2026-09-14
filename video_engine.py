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


def _resolve_ffmpeg():
    exe_name = "ffmpeg.exe" if CURRENT_OS == "windows" else "ffmpeg"
    bundled = BASE_DIR / "ffmpeg-bin" / exe_name
    if bundled.exists():
        return str(bundled)
    found = shutil.which("ffmpeg")
    return found if found else "ffmpeg"


FFMPEG_BIN = _resolve_ffmpeg()
_CLIP_MODEL = None


def get_clip_model():
    global _CLIP_MODEL
    if _CLIP_MODEL is None:
        _CLIP_MODEL = SentenceTransformer("clip-ViT-B-32")
    return _CLIP_MODEL


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
            progress_cb(f"AI scanning {len(new_paths)} media files...", 10)
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
                    new_images, batch_size=32, convert_to_tensor=True, show_progress_bar=False
                )
            for p, emb in zip(processable_paths, new_embeddings):
                cached_dict[str(p.resolve())] = emb.cpu()
            try:
                torch.save(cached_dict, cache_file)
            except Exception:
                pass

    final_paths = []
    final_embeddings_list = []
    for p in current_valid_paths:
        p_str = str(p.resolve())
        if p_str in cached_dict:
            final_paths.append(p)
            final_embeddings_list.append(cached_dict[p_str])

    if not final_embeddings_list:
        return final_paths, None
    return final_paths, torch.stack(final_embeddings_list)


def find_best_image_by_clip(caption_text, valid_paths, image_embeddings, fallback_file, used_paths=None):
    if image_embeddings is None or len(valid_paths) == 0:
        return fallback_file
    clean_text = re.sub(r"<[^>]+>", "", caption_text).strip()
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


def get_render_font(size):
    font_candidates = [
        BASE_DIR / "fonts" / "NamKhone Grand (2).ttf",
        BASE_DIR / "fonts" / "NamKhone Grand.ttf",
        BASE_DIR / "NamKhone Grand.ttf",
        Path("/usr/share/fonts/truetype/noto/NotoSansMyanmar-Bold.ttf"),
        Path("/usr/share/fonts/truetype/noto/NotoSansMyanmar-Regular.ttf"),
        Path("C:/Windows/Fonts/mmrtextb.ttf"),
        Path("C:/Windows/Fonts/mmrtext.ttf"),
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


def split_into_screens_and_lines(raw_text, max_pixel_w, font, max_lines_per_screen=4):
    clean_text = re.sub(r"\r\n|\r", "\n", raw_text).strip()
    first_break = re.search(r"[။\n]", clean_text)
    if first_break:
        split_idx = first_break.end()
        title_part = clean_text[:split_idx].strip()
        body_part = clean_text[split_idx:].strip()
    else:
        title_part = clean_text
        body_part = ""

    screens = []
    dummy_img = Image.new("RGBA", (1, 1))
    draw = ImageDraw.Draw(dummy_img)

    if title_part:
        screens.append([title_part])

    if not body_part:
        return screens

    clauses = [c.strip() for c in re.split(r"(?<=[၊။\n])", body_part) if c.strip()]
    all_lines = []
    curr_line = ""

    for clause in clauses:
        test = f"{curr_line} {clause}".strip() if curr_line else clause
        bbox = draw.textbbox((0, 0), test, font=font)
        if (bbox[2] - bbox[0]) <= max_pixel_w and not clause.endswith("။"):
            curr_line = test
        else:
            if (bbox[2] - bbox[0]) <= max_pixel_w:
                all_lines.append(test)
                curr_line = ""
            else:
                if curr_line:
                    all_lines.append(curr_line)
                words = clause.split(" ")
                sub_w = ""
                for w in words:
                    sub_t = f"{sub_w} {w}".strip() if sub_w else w
                    if (draw.textbbox((0, 0), sub_t, font=font)[2] - draw.textbbox((0, 0), sub_t, font=font)[0]) <= max_pixel_w:
                        sub_w = sub_t
                    else:
                        if sub_w:
                            all_lines.append(sub_w)
                        sub_w = w
                curr_line = sub_w

    if curr_line:
        all_lines.append(curr_line)

    for i in range(0, len(all_lines), max_lines_per_screen):
        chunk = all_lines[i:i + max_lines_per_screen]
        if chunk:
            screens.append(chunk)

    return screens


def hex_to_rgba(hex_code, opacity_pct=100):
    hex_code = str(hex_code).lstrip("#")
    if len(hex_code) == 6:
        r, g, b = tuple(int(hex_code[i:i + 2], 16) for i in (0, 2, 4))
    else:
        r, g, b = 0, 0, 0
    a = int(255 * (float(opacity_pct) / 100.0))
    return (r, g, b, a)


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
    span_regex = re.compile(r"<span([^>]*)>(.*?)</span>", re.IGNORECASE | re.DOTALL)
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
                    "box_bw": 3,
                    "stroke_w": 2,
                    "stroke_c": "#000000",
                })
            elif style_type == "outline":
                blocks.append({
                    "text": content,
                    "is_box": False,
                    "stroke_w": int(attrs.get("data-w", 4)),
                    "stroke_c": attrs.get("data-c", "#000000"),
                })
            else:
                blocks.append({"text": content, "is_box": False, "stroke_w": 4, "stroke_c": "#000000"})
        else:
            plain = clean_html_text(line_clean)
            if plain:
                blocks.append({"text": plain, "is_box": False, "stroke_w": 4, "stroke_c": "#000000"})
    return blocks


def render_caption_image(raw_html, width, height, font_size, line_spacing, output_path, is_mobile=False):
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font_normal = get_render_font(font_size)

    plain_text = clean_html_text(raw_html)
    raw_lines = [l.strip() for l in plain_text.split("\n") if l.strip()]

    if not raw_lines:
        overlay.save(output_path, "PNG")
        return

    flattened_items = []
    total_h = 0

    for l in raw_lines:
        bbox = draw.textbbox((0, 0), l, font=font_normal)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        flattened_items.append({
            "text": l,
            "font": font_normal,
            "tw": tw, "th": th,
        })
        total_h += th + line_spacing

    total_h -= line_spacing
    curr_y = (height - total_h) // 2

    for item in flattened_items:
        f = item["font"]
        txt = item["text"]
        tx = (width - item["tw"]) // 2
        ty = curr_y
        curr_y += item["th"] + line_spacing

        sw = 5
        sc = (0, 0, 0, 255)
        draw.text((tx, ty), txt, font=f, fill=(255, 255, 255, 255), stroke_width=sw, stroke_fill=sc)

    overlay.save(output_path, "PNG")


def create_dimmer_and_logo(width, height, logo_path, opacity_pct, output_path, is_mobile=False):
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    alpha = int(255 * (opacity_pct / 100.0))
    draw.rectangle([0, 0, width, height], fill=(0, 0, 0, alpha))

    if logo_path and os.path.exists(logo_path):
        try:
            logo_img = Image.open(logo_path).convert("RGBA")
            logo_size = int(140 if is_mobile else 120)
            logo_img.thumbnail((logo_size, logo_size), Image.Resampling.LANCZOS)
            pos_x = width - logo_img.width - (50 if is_mobile else 40)
            pos_y = 50 if is_mobile else 35
            overlay.paste(logo_img, (pos_x, pos_y), logo_img)
        except Exception:
            pass
    overlay.save(output_path, "PNG")


def prepare_background_image(img_path, width, height, output_path, is_mobile=False):
    try:
        orig = Image.open(img_path).convert("RGB")
        if is_mobile:
            # 1. Full Blurred Dark Background (9:16)
            scale_bg = max(width / orig.width, height / orig.height)
            bg_w, bg_h = int(orig.width * scale_bg), int(orig.height * scale_bg)
            resized_bg = orig.resize((bg_w, bg_h), Image.Resampling.BILINEAR)
            crop_x = (bg_w - width) // 2
            crop_y = (bg_h - height) // 2
            canvas = resized_bg.crop((crop_x, crop_y, crop_x + width, crop_y + height))
            canvas = canvas.filter(ImageFilter.GaussianBlur(radius=35))
            dark_dim = Image.new("RGB", (width, height), (0, 0, 0))
            canvas = Image.blend(canvas, dark_dim, 0.45)

            # 2. Sharp Center Landscape Banner Frame
            fg_w = width
            fg_h = int(orig.height * (width / orig.width))
            if fg_h > int(height * 0.55):
                fg_h = int(height * 0.55)
            fg_img = orig.resize((fg_w, fg_h), Image.Resampling.BILINEAR)
            
            pos_x = 0
            pos_y = (height - fg_h) // 2
            canvas.paste(fg_img, (pos_x, pos_y))

            # 3. Subtle Border Divider Lines
            draw = ImageDraw.Draw(canvas)
            draw.line([(0, pos_y), (width, pos_y)], fill=(120, 120, 120), width=2)
            draw.line([(0, pos_y + fg_h), (width, pos_y + fg_h)], fill=(120, 120, 120), width=2)

            canvas.save(output_path, "JPEG", quality=92)
        else:
            scale = max(width / orig.width, height / orig.height)
            new_w, new_h = int(orig.width * scale), int(orig.height * scale)
            resized = orig.resize((new_w, new_h), Image.Resampling.BILINEAR)
            crop_x = (new_w - width) // 2
            crop_y = (new_h - height) // 2
            canvas = resized.crop((crop_x, crop_y, crop_x + width, crop_y + height))
            canvas.save(output_path, "JPEG", quality=90)
    except Exception:
        fallback = Image.new("RGB", (width, height), (15, 15, 15))
        fallback.save(output_path, "JPEG")


def render_all_clips(df, media_dir, audio_path, output_file, logo_path, cfg, progress_cb):
    temp_dir = Path(tempfile.mkdtemp(prefix="dhamma_render_"))
    try:
        format_type = cfg.get("format", "landscape")
        is_mobile = (format_type == "mobile")
        width, height = (1080, 1920) if is_mobile else (1920, 1080)

        font_size = int(cfg.get("font_size", 42 if is_mobile else 48))
        line_spacing = int(cfg.get("line_spacing", 22 if is_mobile else 26))
        opacity = int(cfg.get("opacity", 45))
        fps = 12

        enable_bgm_cfg = bool(cfg.get("enable_bgm", True))
        bgm_path = resolve_bgm_path()
        has_intro_bgm = (enable_bgm_cfg and bgm_path and os.path.exists(bgm_path))

        supported_exts = [".jpg", ".jpeg", ".png", ".webp"]
        media_files = sorted(
            [p for p in Path(media_dir).iterdir() if p.is_file() and p.suffix.lower() in supported_exts]
        )
        if not media_files:
            return False, "No background images found."

        progress_cb("Analyzing images with AI CLIP...", 15)
        valid_paths, image_embeddings = scan_and_index_images(media_dir, media_files, progress_cb)

        dimmer_logo_png = temp_dir / "dimmer_logo.png"
        create_dimmer_and_logo(width, height, logo_path, opacity, str(dimmer_logo_png), is_mobile=is_mobile)

        tasks = []
        used_images = set()
        total_rows = len(df)
        progress_cb("Constructing video chunks...", 25)

        for idx, row in df.iterrows():
            st = float(row["start_time"])
            et = float(row["end_time"])
            dur = max(0.5, et - st)
            raw_caption = str(row["caption"]).strip()

            if len(used_images) >= len(valid_paths):
                used_images.clear()
            media_path = find_best_image_by_clip(raw_caption, valid_paths, image_embeddings, media_files[idx % len(media_files)], used_images)
            used_images.add(media_path)

            bg_jpg = temp_dir / f"bg_{idx:04d}.jpg"
            prepare_background_image(media_path, width, height, str(bg_jpg), is_mobile=is_mobile)

            text_png = temp_dir / f"txt_{idx:04d}.png"
            render_caption_image(raw_caption, width, height, font_size, line_spacing, str(text_png), is_mobile=is_mobile)

            clip_mp4 = temp_dir / f"clip_{idx:04d}.mp4"
            include_bgm = (idx == 0 and has_intro_bgm)

            inputs = [
                "-loop", "1", "-framerate", str(fps), "-i", str(bg_jpg),
                "-loop", "1", "-framerate", str(fps), "-i", str(dimmer_logo_png),
                "-loop", "1", "-framerate", str(fps), "-i", str(text_png),
                "-ss", str(st), "-to", str(et), "-i", str(audio_path),
            ]

            if include_bgm:
                inputs += ["-stream_loop", "-1", "-i", str(bgm_path)]
                filter_complex = (
                    "[0:v][1:v]overlay=0:0[bg_dim];"
                    "[2:v]fade=t=in:st=0:d=0.2:alpha=1[text_faded];"
                    "[bg_dim][text_faded]overlay=0:0[v];"
                    "[4:a]volume=0.35[bgm_a];"
                    "[3:a][bgm_a]amix=inputs=2:duration=first:dropout_transition=2[a]"
                )
                map_audio = "[a]"
            else:
                filter_complex = (
                    "[0:v][1:v]overlay=0:0[bg_dim];"
                    "[2:v]fade=t=in:st=0:d=0.2:alpha=1[text_faded];"
                    "[bg_dim][text_faded]overlay=0:0[v]"
                )
                map_audio = "3:a"

            cmd = [
                FFMPEG_BIN, "-y", "-hide_banner", "-loglevel", "error",
                *inputs,
                "-filter_complex", filter_complex,
                "-map", "[v]",
                "-map", map_audio,
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "22", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "128k",
                "-t", str(dur),
                str(clip_mp4)
            ]
            tasks.append((cmd, clip_mp4))

        rendered_clips = []
        with ThreadPoolExecutor(max_workers=min(os.cpu_count() or 2, 4)) as executor:
            futures = [executor.submit(subprocess.run, t[0], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE) for t in tasks]
            for i, f in enumerate(futures):
                res = f.result()
                if res.returncode == 0:
                    rendered_clips.append(tasks[i][1])
                pct = 25 + int(((i + 1) / total_rows) * 65)
                progress_cb(f"Rendering segment {i + 1}/{total_rows}...", pct)

        if not rendered_clips:
            return False, "Failed to render video clips."

        progress_cb("Merging all video clips...", 92)
        concat_txt = temp_dir / "concat.txt"
        with open(concat_txt, "w", encoding="utf-8") as f:
            for c in rendered_clips:
                f.write(f"file '{str(c.resolve()).replace('\\', '/')}'\n")

        merge_cmd = [
            FFMPEG_BIN, "-y", "-hide_banner", "-loglevel", "error",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_txt),
            "-c", "copy",
            "-movflags", "+faststart",
            str(output_file)
        ]
        subprocess.run(merge_cmd, check=True)
        progress_cb("Done! Video ready in Downloads folder.", 100)
        return True, str(output_file)

    except Exception as e:
        return False, str(e)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)