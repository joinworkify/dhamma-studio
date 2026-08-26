import html
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import textwrap
from concurrent.futures import ThreadPoolExecutor
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


def paginate_blocks(blocks, wrap_width, max_lines_per_page=4):
    """
    စာကြောင်းအရေအတွက် စုစုပေါင်း ၄ ကြောင်းထက် မကျော်စေရန် ပိုင်းဖြတ်ပေးသည့် စနစ်
    """
    if not blocks:
        return []

    pages = []
    current_page = []
    current_line_count = 0

    for b in blocks:
        lines = textwrap.wrap(b["text"], width=wrap_width)
        lines_count = max(1, len(lines))

        if lines_count > max_lines_per_page:
            if current_page:
                pages.append(current_page)
                current_page = []
                current_line_count = 0

            for i in range(0, len(lines), max_lines_per_page):
                sub_lines = lines[i : i + max_lines_per_page]
                pages.append([{**b, "text": "\n".join(sub_lines), "_is_prewrapped": True}])
            continue

        if current_line_count + lines_count > max_lines_per_page:
            pages.append(current_page)
            current_page = [b]
            current_line_count = lines_count
        else:
            current_page.append(b)
            current_line_count += lines_count

    if current_page:
        pages.append(current_page)

    return pages


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


def render_blocks_to_image(blocks, width, height, font_size, wrap_width, line_spacing, pos_choice, is_mobile, output_path):
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
        
        if b.get("_is_prewrapped"):
            formatted = b["text"]
        else:
            wrapped = textwrap.wrap(b["text"], width=wrap_width)
            formatted = "\n".join(wrapped)

        bbox = draw.multiline_textbbox((0, 0), formatted, font=curr_font, align="center", spacing=line_spacing)
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


def prepare_final_image_layer(img_path, width, height, is_mobile, output_path):
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
            canvas = canvas.filter(ImageFilter.GaussianBlur(radius=25))

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


def render_single_task(task):
    cmd, clip_mp4 = task
    res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return clip_mp4 if res.returncode == 0 else None


def render_all_clips(df, media_dir, get_audio_path_fn, output_file, logo_path, cfg, progress_cb, bgm_path=""):
    temp_dir = Path(tempfile.mkdtemp(prefix="fast_dhamma_"))
    try:
        is_mobile = cfg.get("format", "landscape") == "mobile"
        width, height = (1080, 1920) if is_mobile else (1920, 1080)
        
        font_size = int(cfg.get("font_size", 38 if is_mobile else 44))
        wrap_width = int(cfg.get("wrap_width", 28 if is_mobile else 38))
        line_spacing = int(cfg.get("line_spacing", 18 if is_mobile else 22))
        pos_choice = cfg.get("position", "middle")
        
        overlay_mode = cfg.get("overlay_mode", "Full Video Overlay")
        rgba_color = hex_to_rgba(cfg.get("color", "#000000"), cfg.get("opacity", 45))

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

        tasks = []
        bgm_start_offset = 10.0  # BGM တီးလုံးကို ၁၀ စက္ကန့်မှ စတင်ဖြတ်ယူခြင်း

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

            blocks = parse_styled_blocks(caption)
            pages = paginate_blocks(blocks, wrap_width=wrap_width, max_lines_per_page=4)
            if not pages:
                pages = [[]]

            clip_mp4 = temp_dir / f"clip_{idx:04d}.mp4"
            include_bgm = (idx == 0 and bgm_path and os.path.exists(bgm_path))

            base_bg_jpg = temp_dir / f"base_bg_{idx:04d}.jpg"
            if not is_video_input:
                prepare_final_image_layer(media_path, width, height, is_mobile, str(base_bg_jpg))

            num_pages = len(pages)

            # စာလုံးရေအလိုက် Weighted Dynamic Timings
            page_char_counts = [max(1, sum(len(b.get("text", "")) for b in page_blocks)) for page_blocks in pages]
            total_chars = sum(page_char_counts)

            page_timings = []
            accumulated_time = 0.0

            for p_idx, count in enumerate(page_char_counts):
                st = accumulated_time
                if p_idx == num_pages - 1:
                    et = audio_dur
                else:
                    dur = (count / total_chars) * audio_dur
                    et = round(st + dur, 2)
                    accumulated_time = et
                page_timings.append((st, et))

            page_pngs = []
            for p_idx, page_blocks in enumerate(pages):
                p_png = temp_dir / f"cap_{idx:04d}_p{p_idx}.png"
                render_blocks_to_image(page_blocks, width, height, font_size, wrap_width, line_spacing, pos_choice, is_mobile, str(p_png))
                page_pngs.append(p_png)

            inputs = []
            if not is_video_input:
                inputs += ["-loop", "1", "-i", str(base_bg_jpg)]
            else:
                inputs += ["-stream_loop", "-1", "-i", str(media_path)]

            inputs += ["-loop", "1", "-i", str(static_overlay_png)]
            for p_png in page_pngs:
                inputs += ["-loop", "1", "-i", str(p_png)]

            inputs += ["-i", str(audio_path)]
            audio_in_idx = 2 + num_pages

            if include_bgm:
                inputs += ["-stream_loop", "-1", "-i", str(bgm_path)]
                bgm_in_idx = audio_in_idx + 1

            filter_parts = []
            if is_video_input:
                filter_parts.append(f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}[base]")
                last_v = "[base]"
            else:
                last_v = "[0:v]"

            filter_parts.append(f"{last_v}[1:v]overlay=0:0[bg_dim]")
            last_bg = "[bg_dim]"

            for p_idx in range(num_pages):
                st, et = page_timings[p_idx]
                cap_in = f"[{2 + p_idx}:v]"
                fade_txt = f"{cap_in}format=yuva420p,fade=t=in:st={st}:d=0.25:alpha=1,fade=t=out:st={max(0, et - 0.25)}:d=0.25:alpha=1[txt_{p_idx}]"
                filter_parts.append(fade_txt)
                
                next_bg = f"[v_step_{p_idx}]" if p_idx < num_pages - 1 else "[v]"
                overlay_step = f"{last_bg}[txt_{p_idx}]overlay=0:0:enable='between(t,{st},{et})'{next_bg}"
                filter_parts.append(overlay_step)
                last_bg = next_bg

            # Audio filter (BGM ကို ၁၀ စက္ကန့်မှ စတင်ဖြတ်ပြီး volume 0.35 ဖြင့် ရောစပ်ခြင်း)
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

            cmd = [
                "ffmpeg", "-y",
                "-threads", "2",
                "-framerate", "24",
            ] + inputs + [
                "-filter_complex", filter_str,
                "-map", "[v]",
                "-map", a_map,
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-tune", "stillimage" if not is_video_input else "fastdecode",
                "-c:a", "aac",
                "-b:a", "128k",
                "-pix_fmt", "yuv420p",
                "-t", str(audio_dur),
                str(clip_mp4),
            ]

            tasks.append((cmd, clip_mp4))

        # Parallel Render
        rendered_clips = []
        max_workers = min(os.cpu_count() or 4, 4)
        completed = 0

        progress_cb("Rendering Clips...", 15)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(render_single_task, t) for t in tasks]
            for future in futures:
                res = future.result()
                completed += 1
                progress_cb(f"Rendered {completed}/{len(tasks)} clips...", 15 + int((completed / len(tasks)) * 75))
                if res:
                    rendered_clips.append(res)

        if not rendered_clips:
            return False, "Failed to render clips. Please check source assets."

        progress_cb("Merging into final video...", 95)
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
            return False, "Error during final video concatenation."

        progress_cb("Rendering Complete!", 100)
        return True, str(output_file)

    except Exception as e:
        return False, str(e)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)