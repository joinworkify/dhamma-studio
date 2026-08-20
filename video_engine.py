import glob
import os
from pathlib import Path
import shutil
import subprocess
import textwrap
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = Path(__file__).resolve().parent


def get_ffmpeg_binary():
  cmd = shutil.which("ffmpeg")
  if cmd:
    return cmd
  try:
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()
  except ImportError:
    pass
  return "ffmpeg"


def get_render_font(size):
  font_candidates = [
      BASE_DIR / "NamKhone Grand (2).ttf",
      BASE_DIR / "fonts" / "NamKhone Grand (2).ttf",
      BASE_DIR / "NamKhone Grand.ttf",
      BASE_DIR / "fonts" / "NamKhone Grand.ttf",
      BASE_DIR / "NamKhone.ttf",
      BASE_DIR / "fonts" / "NamKhone.ttf",
  ]
  for path in font_candidates:
    if path.exists():
      try:
        return ImageFont.truetype(str(path), size)
      except Exception:
        continue

  system_fallbacks = [
      "C:/Windows/Fonts/mmrtext.ttf",
      "/System/Library/Fonts/Supplemental/NotoSansMyanmar.ttc",
      "/usr/share/fonts/truetype/noto/NotoSansMyanmar-Regular.ttf",
      "/usr/share/fonts/truetype/padauk/Padauk.ttf",
  ]
  for sys_path in system_fallbacks:
    if Path(sys_path).exists():
      try:
        return ImageFont.truetype(sys_path, size)
      except Exception:
        continue
  return ImageFont.load_default()


def hex_to_rgba(hex_code, opacity_percent):
  hex_code = hex_code.lstrip("#")
  r = int(hex_code[0:2], 16)
  g = int(hex_code[2:4], 16)
  b = int(hex_code[4:6], 16)
  alpha = int(255 * (opacity_percent / 100))
  return (r, g, b, alpha)


def create_text_overlay(
    text,
    width,
    height,
    font_size,
    wrap_width,
    line_spacing,
    overlay_mode,
    rgba_color,
    pos_choice,
    is_mobile,
    output_path,
):
  overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
  draw = ImageDraw.Draw(overlay)
  font = get_render_font(font_size)

  if overlay_mode == "Full Video Overlay" and rgba_color[3] > 0:
    draw.rectangle([0, 0, width, height], fill=rgba_color)

  if text.strip():
    wrapped = textwrap.wrap(text, width=wrap_width)
    formatted = "\n".join(wrapped)

    bbox = draw.multiline_textbbox(
        (0, 0), formatted, font=font, align="center", spacing=line_spacing
    )
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    box_w = int(width * 0.88)
    pad_y = 26
    box_h = text_h + (pad_y * 2)

    if pos_choice == "high":
      box_y = 120 if not is_mobile else 220
    elif pos_choice == "low":
      box_y = height - box_h - (120 if not is_mobile else 340)
    else:  # middle
      box_y = (height - box_h) // 2

    box_x = (width - box_w) // 2
    text_x = (width - text_w) // 2
    text_y = box_y + pad_y

    if overlay_mode == "Text Box Only" and rgba_color[3] > 0:
      draw.rounded_rectangle(
          [box_x, box_y, box_x + box_w, box_y + box_h],
          radius=14,
          fill=rgba_color,
      )

    draw.multiline_text(
        (text_x, text_y),
        formatted,
        font=font,
        fill=(255, 255, 255, 255),
        align="center",
        spacing=line_spacing,
    )

  overlay.save(output_path, "PNG")


def render_all_clips(
    df, images_dir, get_audio_path_fn, output_video, cfg, progress_callback
):
  temp_dir = BASE_DIR / "temp_render_webview"
  ffmpeg_bin = get_ffmpeg_binary()
  try:
    images = []
    for ext in ("*.png", "*.jpg", "*.jpeg", "*.webp", "*.PNG", "*.JPG"):
      images.extend(Path(images_dir).glob(ext))
    images = sorted(images)
    if not images:
      raise Exception("No valid images found in the selected folder.")

    is_mobile = cfg["format"] == "mobile"
    width, height = (1080, 1920) if is_mobile else (1920, 1080)
    wrap_width = 22 if is_mobile else 44

    font_size = int(cfg.get("font_size", 46))
    line_spacing = int(cfg.get("line_spacing", 20))
    overlay_mode = cfg.get("overlay_mode", "Full Video Overlay")
    pos_choice = cfg.get("position", "middle")
    rgba_color = hex_to_rgba(
        cfg.get("color", "#000000"), float(cfg.get("opacity", 70))
    )

    temp_dir.mkdir(parents=True, exist_ok=True)
    clip_list = temp_dir / "clips.txt"
    valid_clips = []
    total = len(df)

    for idx, row in df.iterrows():
      pct = int(((idx + 1) / total) * 100)
      progress_callback(f"Rendering Clip {idx+1}/{total}...", pct)

      caption = str(row["caption"]).strip() if str(row["caption"]) != "nan" else ""
      mp3_name = str(row["mp3"]).strip()
      audio_path = get_audio_path_fn(mp3_name)

      if not audio_path or not os.path.exists(audio_path):
        continue

      img_path = images[idx % len(images)].resolve()
      text_png = temp_dir / f"text_{idx:04d}.png"
      create_text_overlay(
          caption,
          width,
          height,
          font_size,
          wrap_width,
          line_spacing,
          overlay_mode,
          rgba_color,
          pos_choice,
          is_mobile,
          str(text_png),
      )

      clip_out = temp_dir / f"clip_{idx:04d}.ts"
      vf_filter = (
          f"[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
          f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,format=yuva420p[base];"
          f"[base][1:v]overlay=0:0:format=auto,format=yuv420p"
      )

      cmd = [
          ffmpeg_bin,
          "-y",
          "-loop",
          "1",
          "-i",
          str(img_path),
          "-i",
          str(text_png),
          "-i",
          str(audio_path),
          "-filter_complex",
          vf_filter,
          "-c:v",
          "libx264",
          "-preset",
          "ultrafast",
          "-tune",
          "stillimage",
          "-c:a",
          "aac",
          "-b:a",
          "192k",
          "-shortest",
          "-f",
          "mpegts",
          str(clip_out),
      ]
      res = subprocess.run(
          cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
      )
      if res.returncode == 0 and clip_out.exists():
        valid_clips.append(clip_out)

    if not valid_clips:
      raise Exception("No clips were generated. Check your paths.")

    with open(clip_list, "w", encoding="utf-8") as f:
      for c in valid_clips:
        f.write(f"file '{c.resolve().as_posix()}'\n")

    progress_callback("Merging video segments...", 95)
    out_video = Path(output_video).resolve()

    merge_cmd = [
        ffmpeg_bin,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        clip_list.as_posix(),
        "-c",
        "copy",
        str(out_video),
    ]
    subprocess.run(merge_cmd, check=True)

    shutil.rmtree(temp_dir, ignore_errors=True)
    return True, str(out_video)

  except Exception as err:
    if temp_dir.exists():
      shutil.rmtree(temp_dir, ignore_errors=True)
    return False, str(err)