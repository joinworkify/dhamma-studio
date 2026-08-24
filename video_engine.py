import html
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import textwrap
import mutagen
from PIL import Image, ImageDraw, ImageFont, ImageFilter

BASE_DIR = Path(__file__).resolve().parent


def hex_to_rgba(hex_code, opacity_pct):
    hex_code = str(hex_code).lstrip("#")
    if len(hex_code) == 6:
        r, g, b = tuple(int(hex_code[i : i + 2], 16) for i in (0, 2, 4))
    else:
        r, g, b = 0, 0, 0
    a = int(255 * (float(opacity_pct) / 100.0))
    return (r, g, b, a)


def get_render_font(size):
    font_candidates = [
        BASE_DIR / "fonts" / "NamKhone Grand (2).ttf",
        BASE_DIR / "fonts" / "NamKhone Grand.ttf",
        BASE_DIR / "NamKhone Grand.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansMyanmar-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansMyanmar-Regular.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansMyanmar-Bold.otf",
    ]
    for c in font_candidates:
        if c.exists():
            try:
                return ImageFont.truetype(str(c), size)
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
                bg = attrs.get("data-bg", "#8c4e12")
                bc = attrs.get("data-bc", "#ffffff")
                blocks.append({
                    "text": content,
                    "is_box": True,
                    "box_bg": bg,
                    "box_op": 90,
                    "box_bc": bc,
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
            margin = 35 if not is_mobile else 45
            pos_x = width - logo_img.width - margin
            pos_y = margin
            overlay.paste(logo_img, (pos_x, pos_y), logo_img)
        except Exception:
            pass

    overlay.save(output_path, "PNG")


def create_caption_overlay(
    text,
    width,
    height,
    font_size,
    wrap_width,
    line_spacing,
    pos_choice,
    is_mobile,
    output_path,
):
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    font_normal = get_render_font(font_size)
    font_box = get_render_font(int(font_size * 1.20))

    blocks = parse_styled_blocks(text)
    if not blocks:
        overlay.save(output_path, "PNG")
        return

    rendered_items = []
    total_content_h = 0

    for b in blocks:
        is_box = b["is_box"]
        curr_font = font_box if is_box else font_normal
        wrapped = textwrap.wrap(b["text"], width=wrap_width)
        formatted = "\n".join(wrapped)

        bbox = draw.multiline_textbbox((0, 0), formatted, font=curr_font, align="center", spacing=line_spacing)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]

        pad_x = 36 if is_box else 20
        pad_y = 24 if is_box else 14

        bw = min(int(width * 0.92), tw + (pad_x * 2)) if is_box else tw
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
        start_y = height - total_content_h - (120 if not is_mobile else 300)
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

            box_fill_rgba = hex_to_rgba(b["box_bg"], b["box_op"])
            box_border_rgba = hex_to_rgba(b["box_bc"], 100)

            draw.rectangle(
                [bx, by, bx + item["box_w"], by + item["box_h"]],
                fill=box_fill_rgba,
                outline=box_border_rgba if b["box_bw"] > 0 else None,
                width=b["box_bw"],
            )

            tx = (width - item["text_w"]) // 2
            ty = by + item["pad_y"]
            curr_y += item["box_h"] + line_spacing
        else:
            tx = (width - item["text_w"]) // 2
            ty = curr_y
            curr_y += item["text_h"] + line_spacing

        s_w = b.get("stroke_w", 0)
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


def prepare_final_image_layer(img_path, width, height, is_mobile, output_path):
    """
    Instantly creates the base canvas with blurred top/bottom and sharp centered foreground.
    """
    try:
        orig = Image.open(img_path).convert("RGB")
        if is_mobile:
            # 1. Background Blurred Fill
            scale_bg = max(width / orig.width, height / orig.height)
            bg_w = int(orig.width * scale_bg)
            bg_h = int(orig.height * scale_bg)
            resized_bg = orig.resize((bg_w, bg_h), Image.Resampling.BILINEAR)
            crop_x = (bg_w - width) // 2
            crop_y = (bg_h - height) // 2
            canvas = resized_bg.crop((crop_x, crop_y, crop_x + width, crop_y + height))
            canvas = canvas.filter(ImageFilter.GaussianBlur(radius=25))

            # 2. Centered Sharp Foreground (Original Aspect Ratio)
            scale_fg = min(width / orig.width, height / orig.height)
            fg_w = int(orig.width * scale_fg)
            fg_h = int(orig.height * scale_fg)
            fg_img = orig.resize((fg_w, fg_h), Image.Resampling.LANCZOS)
            pos_x = (width - fg_w) // 2
            pos_y = (height - fg_h) // 2

            canvas.paste(fg_img, (pos_x, pos_y))
            canvas.save(output_path, "JPEG", quality=90)
        else:
            scale = max(width / orig.width, height / orig.height)
            new_w = int(orig.width * scale)
            new_h = int(orig.height * scale)
            resized = orig.resize((new_w, new_h), Image.Resampling.LANCZOS)
            crop_x = (new_w - width) // 2
            crop_y = (new_h - height) // 2
            canvas = resized.crop((crop_x, crop_y, crop_x + width, crop_y + height))
            canvas.save(output_path, "JPEG", quality=90)
    except Exception:
        fallback = Image.new("RGB", (width, height), (20, 20, 20))
        fallback.save(output_path, "JPEG")


def build_caption_filter(anim_type, input_label, output_label):
    dur = 0.3
    if anim_type == "fade_in":
        return f"{input_label}format=yuva420p,fade=t=in:st=0:d={dur}:alpha=1{output_label};"
    elif anim_type == "soft_zoom":
        return (
            f"{input_label}format=yuva420p,"
            f"zoompan=z='if(lte(on,8), 1.02-0.02*(on/8), 1.0)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':fps=24,"
            f"fade=t=in:st=0:d={dur}:alpha=1{output_label};"
        )
    elif anim_type == "slide_up" or anim_type == "slide_down" or anim_type == "blur_in":
        return f"{input_label}format=yuva420p,fade=t=in:st=0:d={dur}:alpha=1{output_label};"
    else:
        return f"{input_label}format=yuva420p{output_label};"


def render_all_clips(df, media_dir, get_audio_path_fn, output_file, logo_path, cfg, progress_cb):
    temp_dir = Path(tempfile.mkdtemp(prefix="fast_dhamma_"))
    try:
        is_mobile = cfg.get("format", "landscape") == "mobile"
        width, height = (1080, 1920) if is_mobile else (1920, 1080)
        font_size = int(cfg.get("font_size", 42 if is_mobile else 46))
        wrap_width = int(32 if is_mobile else 38)
        line_spacing = int(18 if is_mobile else 20)
        pos_choice = cfg.get("position", "middle")
        
        overlay_mode = cfg.get("overlay_mode", "Full Video Overlay")
        rgba_color = hex_to_rgba(cfg.get("color", "#000000"), cfg.get("opacity", 45))
        caption_anim = cfg.get("caption_anim", "fade_in")

        supported_exts = [".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mov", ".mkv", ".avi", ".webm"]
        video_exts = [".mp4", ".mov", ".mkv", ".avi", ".webm"]

        media_files = sorted(
            [p for p in Path(media_dir).iterdir() if p.suffix.lower() in supported_exts]
        )
        if not media_files:
            return False, f"No image/video files found in '{media_dir}'"

        static_overlay_png = temp_dir / "static_dimmer_overlay.png"
        create_static_dimmer_overlay(
            width,
            height,
            is_mobile,
            str(static_overlay_png),
            logo_path=logo_path,
            overlay_mode=overlay_mode,
            rgba_color=rgba_color,
        )

        rendered_clips = []
        total = len(df)

        for idx, row in df.iterrows():
            caption = str(row["caption"]).strip() if str(row["caption"]) != "nan" else ""
            mp3_name = str(row["mp3"]).strip()

            audio_path = get_audio_path_fn(mp3_name)
            if not audio_path or not os.path.exists(audio_path):
                continue

            try:
                audio_dur = max(mutagen.File(audio_path).info.length, 1.0)
            except Exception:
                audio_dur = 5.0

            media_path = media_files[idx % len(media_files)]
            is_video_input = media_path.suffix.lower() in video_exts

            caption_png = temp_dir / f"caption_{idx:04d}.png"
            clip_mp4 = temp_dir / f"clip_{idx:04d}.mp4"

            create_caption_overlay(
                caption,
                width,
                height,
                font_size,
                wrap_width,
                line_spacing,
                pos_choice,
                is_mobile,
                str(caption_png),
            )

            txt_filter = build_caption_filter(caption_anim, "[2:v]", "[txt]")
            txt_src = "[txt]"

            if not is_video_input:
                base_bg_jpg = temp_dir / f"base_bg_{idx:04d}.jpg"
                prepare_final_image_layer(media_path, width, height, is_mobile, str(base_bg_jpg))

                cmd = [
                    "ffmpeg", "-y",
                    "-threads", "0",
                    "-framerate", "24",
                    "-loop", "1", "-i", str(base_bg_jpg),
                    "-loop", "1", "-i", str(static_overlay_png),
                    "-loop", "1", "-i", str(caption_png),
                    "-i", str(audio_path),
                    "-filter_complex", (
                        f"{txt_filter}"
                        f"[0:v][1:v]overlay=0:0[bg_dim];"
                        f"[bg_dim]{txt_src}overlay=0:0[v]"
                    ),
                    "-map", "[v]",
                    "-map", "3:a",
                    "-c:v", "libx264",
                    "-preset", "ultrafast",
                    "-tune", "stillimage",
                    "-c:a", "aac",
                    "-b:a", "128k",
                    "-pix_fmt", "yuv420p",
                    "-t", str(audio_dur),
                    str(clip_mp4),
                ]
            else:
                cmd = [
                    "ffmpeg", "-y",
                    "-threads", "0",
                    "-stream_loop", "-1", "-i", str(media_path),
                    "-loop", "1", "-i", str(static_overlay_png),
                    "-loop", "1", "-i", str(caption_png),
                    "-i", str(audio_path),
                    "-filter_complex", (
                        f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}[base];"
                        f"{txt_filter}"
                        f"[base][1:v]overlay=0:0[bg_dim];"
                        f"[bg_dim]{txt_src}overlay=0:0[v]"
                    ),
                    "-map", "[v]",
                    "-map", "3:a",
                    "-c:v", "libx264",
                    "-preset", "ultrafast",
                    "-c:a", "aac",
                    "-b:a", "128k",
                    "-pix_fmt", "yuv420p",
                    "-t", str(audio_dur),
                    str(clip_mp4),
                ]

            progress_cb(f"Rendering Clip {idx + 1}/{total}...", int((idx / total) * 90))
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if res.returncode == 0:
                rendered_clips.append(clip_mp4)

        if not rendered_clips:
            return False, "Failed to render video clips. Please check audio/media files."

        progress_cb("Merging clips into final video...", 95)
        concat_txt = temp_dir / "concat_list.txt"
        with open(concat_txt, "w", encoding="utf-8") as f:
            for c in rendered_clips:
                f.write(f"file '{c.resolve()}'\n")

        merge_cmd = [
            "ffmpeg", "-y",
            "-threads", "0",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_txt),
            "-c", "copy",
            str(output_file),
        ]
        res = subprocess.run(merge_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if res.returncode != 0:
            return False, "FFmpeg error during final video merge."

        progress_cb("Rendering Complete!", 100)
        return True, str(output_file)

    except Exception as e:
        return False, str(e)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)