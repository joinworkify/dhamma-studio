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

BASE_DIR = Path(__file__).resolve().parent
CURRENT_OS = platform.system().lower()  # 'darwin' (Mac), 'windows', 'linux'


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
        # macOS Paths
        Path("/System/Library/Fonts/Supplemental/NotoSansMyanmar.ttc"),
        Path("/System/Library/Fonts/Supplemental/NotoSerifMyanmar.ttc"),
        Path("/Library/Fonts/NotoSansMyanmar-Regular.ttf"),
        # Linux Paths
        Path("/usr/share/fonts/truetype/noto/NotoSansMyanmar-Bold.ttf"),
        Path("/usr/share/fonts/truetype/noto/NotoSansMyanmar-Regular.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansMyanmar-Bold.otf"),
        # Windows Paths
        Path("C:/Windows/Fonts/mmrtext.ttf"),
        Path("C:/Windows/Fonts/mmrtextb.ttf"),
        Path("C:/Windows/Fonts/NotoSansMyanmar-Regular.ttf"),
    ]

    for c in font_candidates:
        c_path = Path(c)
        if c_path.exists():
            # မြန်မာစာ ဗျည်းတွဲ/အသတ်များ မလွဲစေရန် RAQM shaping engine ဖြင့် အရင်ကြိုးစားမည်
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


def paginate_strictly_by_lines(
    blocks,
    width,
    font_size,
    max_lines_per_page=2
):
    if not blocks:
        return []

    font = get_render_font(font_size)
    max_pixel_w = int(width * 0.76)

    pages = []

    for b in blocks:
        lines = break_lines_by_natural_delimiters(
            b["text"],
            max_pixel_w,
            font
        )

        for i in range(0, len(lines), max_lines_per_page):
            sub_chunk = lines[i:i + max_lines_per_page]
            pages.append([
                {
                    **b,
                    "text": "\n".join(sub_chunk),
                    "_is_prewrapped": True
                }
            ])

    return pages


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
        draw.rectangle(
            [0, 0, width, height],
            fill=rgba_color
        )

    if logo_path and os.path.exists(logo_path):
        try:
            logo_img = Image.open(logo_path).convert("RGBA")
            logo_size = int(110 if is_mobile else 140)
            logo_img.thumbnail(
                (logo_size, logo_size),
                Image.Resampling.LANCZOS
            )

            margin = 35 if not is_mobile else 45
            pos_x = width - logo_img.width - margin
            pos_y = margin

            overlay.paste(
                logo_img,
                (pos_x, pos_y),
                logo_img
            )
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
        is_box = b["is_box"]
        curr_font = font_box if is_box else font_normal
        formatted = b["text"]

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
        start_y = height - total_content_h - (
            120 if not is_mobile else 280
        )
    else:
        start_y = (height - total_content_h) // 2

    curr_y = start_y

    for item in rendered_items:
        fmt = item["formatted"]
        font = item["font"]
        b = item["block_meta"]
        is_box = b["is_box"]

        if is_box:
            bx = (width - item["box_w"]) // 2
            by = curr_y

            box_fill_rgba = hex_to_rgba(
                b["box_bg"],
                b["box_op"]
            )
            box_border_rgba = hex_to_rgba(
                b["box_bc"],
                100
            )

            draw.rectangle(
                [
                    bx,
                    by,
                    bx + item["box_w"],
                    by + item["box_h"]
                ],
                fill=box_fill_rgba,
                outline=(
                    box_border_rgba
                    if b["box_bw"] > 0
                    else None
                ),
                width=b["box_bw"],
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
            scale_bg = max(
                width / orig.width,
                height / orig.height
            )

            bg_w = int(orig.width * scale_bg)
            bg_h = int(orig.height * scale_bg)

            resized_bg = orig.resize(
                (bg_w, bg_h),
                Image.Resampling.BILINEAR
            )

            crop_x = (bg_w - width) // 2
            crop_y = (bg_h - height) // 2

            canvas = resized_bg.crop(
                (
                    crop_x,
                    crop_y,
                    crop_x + width,
                    crop_y + height
                )
            )

            canvas = canvas.filter(
                ImageFilter.GaussianBlur(radius=20)
            )

            scale_fg = min(
                width / orig.width,
                height / orig.height
            )

            fg_w = int(orig.width * scale_fg)
            fg_h = int(orig.height * scale_fg)

            fg_img = orig.resize(
                (fg_w, fg_h),
                Image.Resampling.BILINEAR
            )

            pos_x = (width - fg_w) // 2
            pos_y = (height - fg_h) // 2

            canvas.paste(
                fg_img,
                (pos_x, pos_y)
            )

            canvas.save(
                output_path,
                "JPEG",
                quality=85
            )
        else:
            scale = max(
                width / orig.width,
                height / orig.height
            )

            new_w = int(orig.width * scale)
            new_h = int(orig.height * scale)

            resized = orig.resize(
                (new_w, new_h),
                Image.Resampling.BILINEAR
            )

            crop_x = (new_w - width) // 2
            crop_y = (new_h - height) // 2

            canvas = resized.crop(
                (
                    crop_x,
                    crop_y,
                    crop_x + width,
                    crop_y + height
                )
            )

            canvas.save(
                output_path,
                "JPEG",
                quality=85
            )

    except Exception as err:
        fallback = Image.new(
            "RGB",
            (width, height),
            (20, 20, 20)
        )
        fallback.save(
            output_path,
            "JPEG"
        )


# ============================================================
# CROSS-PLATFORM ENCODER DETECTION
# ============================================================

def ffmpeg_has_encoder(encoder_name):
    try:
        test_cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "error",
            "-f", "lavfi",
            "-i", "nullsrc=s=64x64:d=0.05",
            "-c:v", encoder_name,
            "-f", "null",
            "-"
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

    # AUTO DETECTION ACCORDING TO OS
    if CURRENT_OS == "darwin" and ffmpeg_has_encoder("h264_videotoolbox"):
        return "videotoolbox"
    elif ffmpeg_has_encoder("h264_nvenc"):
        return "nvenc"
    elif ffmpeg_has_encoder("h264_qsv"):
        return "qsv"

    return "x264"


def encoder_args(encoder):
    if encoder == "videotoolbox":
        return [
            "-c:v", "h264_videotoolbox",
            "-b:v", "4500k",
            "-pix_fmt", "yuv420p",
        ]
    if encoder == "nvenc":
        return [
            "-c:v", "h264_nvenc",
            "-preset", "p1",
            "-rc", "vbr",
            "-cq", "23",
            "-b:v", "0",
            "-pix_fmt", "yuv420p",
        ]
    if encoder == "qsv":
        return [
            "-c:v", "h264_qsv",
            "-global_quality", "23",
            "-pix_fmt", "nv12",
        ]

    return [
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "22",
        "-pix_fmt", "yuv420p",
    ]


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
    temp_dir = Path(
        tempfile.mkdtemp(
            prefix="dhamma_render_"
        )
    )

    try:
        is_mobile = (cfg.get("format", "landscape") == "mobile")

        width, height = (1080, 1920) if is_mobile else (1920, 1080)
        font_size = int(cfg.get("font_size", 38 if is_mobile else 44))
        line_spacing = int(cfg.get("line_spacing", 18 if is_mobile else 22))
        pos_choice = cfg.get("position", "middle")
        max_lines = max(1, int(cfg.get("max_lines", cfg.get("lines_per_page", 2))))
        overlay_mode = cfg.get("overlay_mode", "Full Video Overlay")
        rgba_color = hex_to_rgba(cfg.get("color", "#000000"), cfg.get("opacity", 45))
        fps = max(1, int(cfg.get("fps", 12)))

        encoder = choose_encoder(cfg)
        requested_workers = int(cfg.get("render_workers", 0))

        if requested_workers > 0:
            max_workers = requested_workers
        elif encoder in ("nvenc", "videotoolbox"):
            max_workers = 2 if encoder == "videotoolbox" else 1
        else:
            max_workers = min(os.cpu_count() or 2, 4)

        supported_exts = [
            ".jpg", ".jpeg", ".png", ".webp",
            ".mp4", ".mov", ".mkv", ".avi", ".webm"
        ]
        video_exts = [".mp4", ".mov", ".mkv", ".avi", ".webm"]

        # Mac (.DS_Store) နှင့် Windows system files များကို ignore လုပ်ပေးထားသည်
        media_files = sorted(
            [
                p for p in Path(media_dir).iterdir()
                if p.is_file() and not p.name.startswith((".", "~$")) and p.suffix.lower() in supported_exts
            ]
        )

        if not media_files:
            return (
                False,
                f"No image/video files found in '{media_dir}'"
            )

        static_overlay_png = (temp_dir / "static_dimmer_overlay.png")

        create_static_dimmer_overlay(
            width,
            height,
            is_mobile,
            str(static_overlay_png),
            logo_path=logo_path,
            overlay_mode=overlay_mode,
            rgba_color=rgba_color,
        )

        background_cache = {}
        tasks = []
        bgm_start_offset = 10.0

        for row_number, (_, row) in enumerate(df.iterrows()):
            caption = str(row["caption"]).strip() if str(row["caption"]) != "nan" else ""
            mp3_name = str(row["mp3"]).strip()
            audio_path = get_audio_path_fn(mp3_name)

            if not audio_path or not os.path.exists(audio_path):
                continue

            try:
                audio_info = mutagen.File(audio_path)
                audio_dur = max(float(audio_info.info.length), 1.0)
            except Exception:
                audio_dur = 5.0

            media_path = media_files[row_number % len(media_files)]
            is_video_input = media_path.suffix.lower() in video_exts

            blocks = parse_styled_blocks(caption)
            pages = paginate_strictly_by_lines(
                blocks,
                width=width,
                font_size=font_size,
                max_lines_per_page=max_lines,
            )

            if not pages:
                pages = [[]]

            clip_mp4 = (temp_dir / f"clip_{row_number:04d}.mp4")
            include_bgm = (row_number == 0 and bgm_path and os.path.exists(bgm_path))
            base_bg_jpg = None

            if not is_video_input:
                cache_key = (str(media_path.resolve()), width, height, is_mobile)

                if cache_key not in background_cache:
                    cached_path = (temp_dir / f"bg_cache_{len(background_cache):04d}.jpg")
                    prepare_final_image_layer(
                        media_path,
                        width,
                        height,
                        is_mobile,
                        str(cached_path),
                    )
                    background_cache[cache_key] = cached_path

                base_bg_jpg = background_cache[cache_key]

            num_pages = len(pages)
            page_char_counts = [
                max(1, sum(len(b.get("text", "")) for b in page_blocks))
                for page_blocks in pages
            ]
            total_chars = sum(page_char_counts)

            page_timings = []
            accumulated_time = 0.0

            for p_idx, count in enumerate(page_char_counts):
                st = accumulated_time
                if p_idx == num_pages - 1:
                    et = audio_dur
                else:
                    dur = (count / total_chars) * audio_dur
                    et = round(st + dur, 3)
                    accumulated_time = et
                page_timings.append((st, et))

            page_pngs = []
            for p_idx, page_blocks in enumerate(pages):
                p_png = temp_dir / f"cap_{row_number:04d}_p{p_idx}.png"
                render_blocks_to_image(
                    page_blocks,
                    width,
                    height,
                    font_size,
                    line_spacing,
                    pos_choice,
                    is_mobile,
                    str(p_png),
                )
                page_pngs.append(p_png)

            inputs = []
            if not is_video_input:
                inputs += ["-loop", "1", "-framerate", str(fps), "-i", str(base_bg_jpg)]
            else:
                inputs += ["-stream_loop", "-1", "-i", str(media_path)]

            inputs += ["-loop", "1", "-framerate", str(fps), "-i", str(static_overlay_png)]

            for p_png in page_pngs:
                inputs += ["-loop", "1", "-framerate", str(fps), "-i", str(p_png)]

            inputs += ["-i", str(audio_path)]
            audio_in_idx = 2 + num_pages
            bgm_in_idx = None

            if include_bgm:
                inputs += ["-stream_loop", "-1", "-i", str(bgm_path)]
                bgm_in_idx = audio_in_idx + 1

            # ----------------------------------------------------
            # Video filter graph
            # ----------------------------------------------------
            filter_parts = []
            if is_video_input:
                filter_parts.append(
                    f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
                    f"crop={width}:{height},fps={fps}[base]"
                )
                last_v = "[base]"
            else:
                last_v = "[0:v]"

            filter_parts.append(f"{last_v}[1:v]overlay=0:0[bg_dim]")
            last_bg = "[bg_dim]"
            fade_dur = 0.35

            for p_idx in range(num_pages):
                st, et = page_timings[p_idx]
                in_idx = 2 + p_idx
                next_bg = f"[v_step_{p_idx}]" if p_idx < num_pages - 1 else "[v]"

                filter_parts.append(
                    f"[{in_idx}:v]format=yuva420p,fade=t=in:st={st}:d={fade_dur}:alpha=1[cap_anim_{p_idx}]"
                )
                filter_parts.append(
                    f"{last_bg}[cap_anim_{p_idx}]overlay=0:0:enable='between(t,{st},{et})'{next_bg}"
                )
                last_bg = next_bg

            if include_bgm:
                audio_filter = (
                    f"[{audio_in_idx}:a]volume=1.0[v_main];"
                    f"[{bgm_in_idx}:a]atrim=start={bgm_start_offset},asetpts=PTS-STARTPTS,volume=0.35[v_bgm];"
                    f"[v_main][v_bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]"
                )
                filter_parts.append(audio_filter)
                a_map = "[aout]"
            else:
                a_map = f"{audio_in_idx}:a"

            filter_str = ";".join(filter_parts)
            v_encoder_args = encoder_args(encoder)

            cmd = [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel", "error",
            ] + inputs + [
                "-filter_complex", filter_str,
                "-map", "[v]",
                "-map", a_map,
                "-r", str(fps),
            ] + v_encoder_args + [
                "-c:a", "aac",
                "-b:a", "128k",
                "-t", str(audio_dur),
                "-movflags", "+faststart",
                str(clip_mp4),
            ]

            tasks.append((cmd, clip_mp4))

        if not tasks:
            return (False, "No valid audio clips were found.")

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
            return (False, "Failed to render clips. Please check source assets." + detail)

        progress_cb("Merging into final video...", 95)

        concat_txt = temp_dir / "concat_list.txt"
        with open(concat_txt, "w", encoding="utf-8") as f:
            for c in rendered_clips:
                # Windows path compatibility for FFmpeg concat safe format
                safe_path = str(c.resolve()).replace("\\", "/")
                f.write(f"file '{safe_path}'\n")

        merge_cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel", "error",
            "-f", "concat",
            "-safe", "0",
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
            return (False, f"Error during final video concatenation:\n{res.stderr[-5000:]}")

        progress_cb("Rendering Complete!", 100)
        return (True, str(output_file))

    except Exception as e:
        return False, str(e)

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)