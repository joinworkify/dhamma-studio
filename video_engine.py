
import os
import re
import html
import shutil
import platform
import subprocess
import tempfile
import sys
import warnings
import threading

from pathlib import Path
from collections import Counter
from concurrent.futures import ThreadPoolExecutor


# ============================================================
# WINDOWS DLL SETUP
# Must happen BEFORE importing Pillow.
# ============================================================

_FRIBIDI_DLL_HANDLE = None

if sys.platform == "win32":
    if getattr(sys, "frozen", False):
        _RESOURCE_DIR = Path(
            getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent)
        )
    else:
        _RESOURCE_DIR = Path(__file__).resolve().parent

    _FRIBIDI_DLL_DIR = (
        _RESOURCE_DIR / "runtime" / "windows" / "x64"
    )

    if _FRIBIDI_DLL_DIR.is_dir():
        try:
            _FRIBIDI_DLL_HANDLE = os.add_dll_directory(
                str(_FRIBIDI_DLL_DIR.resolve())
            )
        except OSError as exc:
            warnings.warn(
                f"Could not register FriBiDi DLL directory: {exc}"
            )


# ============================================================
# IMPORTS
# ============================================================

from PIL import Image, ImageDraw, ImageFont, ImageFilter
from PIL import features

from sentence_transformers import SentenceTransformer, util
import torch


# ============================================================
# RAQM CHECK
# ============================================================

RAQM_AVAILABLE = False

try:
    RAQM_AVAILABLE = features.check_feature("raqm")
except Exception:
    RAQM_AVAILABLE = False

if not RAQM_AVAILABLE:
    warnings.warn(
        "Pillow RAQM is unavailable. "
        "Myanmar text may not render correctly. "
        "Check Pillow RAQM, HarfBuzz and FriBiDi dependencies."
    )


def load_caption_font(font_path, font_size):
    """
    Load caption font using RAQM when available.
    Falls back to BASIC only when RAQM cannot be used.
    """

    if font_path and os.path.exists(font_path):
        if RAQM_AVAILABLE:
            try:
                return ImageFont.truetype(
                    font_path,
                    font_size,
                    layout_engine=ImageFont.Layout.RAQM
                )
            except Exception as exc:
                warnings.warn(f"RAQM font loading failed: {exc}")

        return ImageFont.truetype(font_path, font_size)

    return ImageFont.load_default()


# ============================================================
# RESOURCE DIRECTORIES
# ============================================================

if getattr(sys, "frozen", False):

    BASE_DIR = Path(
        getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent)
    )

    if sys.platform == "win32":
        APP_DATA_DIR = (
            Path(
                os.environ.get(
                    "LOCALAPPDATA",
                    Path.home() / "AppData" / "Local"
                )
            )
            / "Dhamma Studio"
        )

    elif sys.platform == "darwin":
        APP_DATA_DIR = (
            Path.home()
            / "Library"
            / "Application Support"
            / "Dhamma Studio"
        )

    else:
        APP_DATA_DIR = (
            Path.home()
            / ".local"
            / "share"
            / "Dhamma Studio"
        )

else:
    BASE_DIR = Path(__file__).resolve().parent
    APP_DATA_DIR = BASE_DIR


CURRENT_OS = platform.system().lower()

CACHE_DIR = APP_DATA_DIR / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

_CLIP_MODEL = None


# ============================================================
# CLIP MODEL
# ============================================================

CLIP_REPO = "sentence-transformers/clip-ViT-B-32"
CLIP_DOWNLOAD_BYTES = 606_700_000  # approx. size, used only for progress %
CLIP_DOWNLOAD_DIR = APP_DATA_DIR / "models" / "clip-ViT-B-32"

_CLIP_STATUS = {"state": "missing", "pct": 0, "msg": "AI image model not downloaded"}
_CLIP_LOCK = threading.Lock()


def _clip_dir_valid(path: Path) -> bool:
    """A usable SentenceTransformer folder with full-size weights."""

    try:

        if not (path / "modules.json").exists():
            return False

        weights = list(path.rglob("model.safetensors"))

        return bool(weights) and max(
            w.stat().st_size for w in weights
        ) > 500_000_000

    except OSError:
        return False


def clip_model_path():
    """Bundled model (if any), else the downloaded one, else None."""

    for candidate in (
        BASE_DIR / "models" / "clip-ViT-B-32",
        CLIP_DOWNLOAD_DIR,
    ):
        if _clip_dir_valid(candidate):
            return candidate

    return None


def clip_model_ready() -> bool:
    return clip_model_path() is not None


def get_clip_model_status():

    if clip_model_ready():
        return {"state": "ready", "pct": 100, "msg": "AI image model ready"}

    with _CLIP_LOCK:
        return dict(_CLIP_STATUS)


def _dir_bytes(path: Path) -> int:

    total = 0

    try:
        for f in path.rglob("*"):
            try:
                if f.is_file():
                    total += f.stat().st_size
            except OSError:
                pass
    except OSError:
        pass

    return total


def start_clip_download():
    """Download the CLIP model in the background (resumable, idempotent)."""

    if clip_model_ready():
        return False

    with _CLIP_LOCK:

        if _CLIP_STATUS["state"] == "downloading":
            return False

        _CLIP_STATUS.update(
            state="downloading",
            pct=0,
            msg="Downloading AI image model (~600 MB)..."
        )

    def worker():

        done = threading.Event()

        def watch():

            while not done.is_set():

                pct = min(
                    99,
                    int(_dir_bytes(CLIP_DOWNLOAD_DIR) / CLIP_DOWNLOAD_BYTES * 100)
                )

                with _CLIP_LOCK:
                    _CLIP_STATUS.update(
                        pct=pct,
                        msg=f"Downloading AI image model... {pct}%"
                    )

                done.wait(1.0)

        threading.Thread(target=watch, daemon=True).start()

        try:

            from huggingface_hub import snapshot_download

            CLIP_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

            snapshot_download(
                repo_id=CLIP_REPO,
                local_dir=str(CLIP_DOWNLOAD_DIR),
                ignore_patterns=[
                    "*pytorch_model.bin",
                    "README.md",
                    ".gitattributes"
                ]
            )

            if not _clip_dir_valid(CLIP_DOWNLOAD_DIR):
                raise RuntimeError("Downloaded model files look incomplete.")

            global _CLIP_MODEL
            _CLIP_MODEL = None

            with _CLIP_LOCK:
                _CLIP_STATUS.update(
                    state="ready",
                    pct=100,
                    msg="AI image model ready"
                )

        except Exception as exc:

            with _CLIP_LOCK:
                _CLIP_STATUS.update(
                    state="error",
                    pct=0,
                    msg=f"Model download failed: {str(exc)[:160]}"
                )

        finally:
            done.set()

    threading.Thread(target=worker, daemon=True).start()

    return True


def get_clip_model():
    global _CLIP_MODEL

    if _CLIP_MODEL is None:

        path = clip_model_path()

        if path is None:
            raise RuntimeError("AI image model is not downloaded yet.")

        _CLIP_MODEL = SentenceTransformer(str(path))

    return _CLIP_MODEL


# ============================================================
# FFMPEG
# ============================================================

def _resolve_ffmpeg():

    exe_name = (
        "ffmpeg.exe"
        if CURRENT_OS == "windows"
        else "ffmpeg"
    )

    bundled = BASE_DIR / "ffmpeg-bin" / exe_name

    if bundled.exists():
        return str(bundled)

    found = shutil.which("ffmpeg")

    return found if found else "ffmpeg"


FFMPEG_BIN = _resolve_ffmpeg()


# ============================================================
# FONT RESOLUTION
# ============================================================

def resolve_font_path(target_lang: str = "my"):

    lang = (target_lang or "my").lower().strip()

    if "ja" in lang or "japan" in lang:

        candidates = [
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf"),
            Path("/usr/share/fonts/truetype/takao-gothic/TakaoPGothic.ttf"),
            BASE_DIR / "fonts" / "NotoSansJP-Regular.ttf",
            Path("/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"),
            Path("/System/Library/Fonts/ヒラギノ角ゴシック W5.ttc"),
            Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
            Path("/Library/Fonts/Arial Unicode.ttf"),
            Path("C:/Windows/Fonts/YuGothB.ttc"),
            Path("C:/Windows/Fonts/meiryob.ttc"),
            Path("C:/Windows/Fonts/msgothic.ttc"),
        ]

    elif "zh" in lang or "cn" in lang or "tw" in lang:

        candidates = [
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
            BASE_DIR / "fonts" / "NotoSansSC-Regular.ttf",
            Path("/System/Library/Fonts/PingFang.ttc"),
            Path("/System/Library/Fonts/STHeiti Medium.ttc"),
            Path("/System/Library/Fonts/Hiragino Sans GB.ttc"),
            Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
            Path("C:/Windows/Fonts/msyh.ttc"),
        ]

    elif "ko" in lang or "korean" in lang:

        candidates = [
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
            BASE_DIR / "fonts" / "NotoSansKR-Regular.ttf",
            Path("/System/Library/Fonts/AppleSDGothicNeo.ttc"),
            Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
            Path("C:/Windows/Fonts/malgunbd.ttf"),
            Path("C:/Windows/Fonts/malgun.ttf"),
        ]

    elif "th" in lang or "thai" in lang:

        candidates = [
            Path("/usr/share/fonts/truetype/noto/NotoSansThai-Regular.ttf"),
            Path("/usr/share/fonts/truetype/thai/Loma.ttf"),
            Path("/usr/share/fonts/truetype/tlwg/Loma.ttf"),
            BASE_DIR / "fonts" / "NotoSansThai-Regular.ttf",
            Path("/System/Library/Fonts/ThonburiUI.ttc"),
            Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
            Path("C:/Windows/Fonts/leelawad.ttf"),
        ]

    elif lang in ["en", "vi", "es", "tl", "fr", "de"]:

        candidates = [
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"),
            Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
            Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
            Path("/System/Library/Fonts/Helvetica.ttc"),
            Path("C:/Windows/Fonts/arialbd.ttf"),
            Path("C:/Windows/Fonts/arial.ttf"),
        ]

    else:

        candidates = [
            BASE_DIR / "fonts" / "NamKhone Grand (2).ttf",
            BASE_DIR / "fonts" / "NamKhone Grand.ttf",
            BASE_DIR / "fonts" / "NamKhoneGrand.ttf",
            BASE_DIR / "NamKhone Grand.ttf",
            Path("/usr/share/fonts/truetype/noto/NotoSansMyanmar-Bold.ttf"),
            Path("/usr/share/fonts/truetype/noto/NotoSansMyanmar-Regular.ttf"),
            Path("C:/Windows/Fonts/mmrtextb.ttf"),
            Path("C:/Windows/Fonts/mmrtext.ttf"),
        ]

    for path in candidates:
        if path.exists():
            return str(path.resolve())

    fallback_candidates = [
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ]

    for path in fallback_candidates:
        if path.exists():
            return str(path.resolve())

    return ""


# Pick the font from the text itself (not only the language dropdown), so a line in
# Japanese / Chinese / Korean / Thai / Arabic / Hindi / ... is never drawn with the
# Myanmar font (which shows empty boxes for those scripts).
_SCRIPT_RANGES = [
    ("my", [(0x1000, 0x109F), (0xA9E0, 0xA9FF), (0xAA60, 0xAA7F)]),
    ("ja", [(0x3040, 0x30FF), (0x31F0, 0x31FF), (0xFF66, 0xFF9F)]),
    ("ko", [(0xAC00, 0xD7AF), (0x1100, 0x11FF), (0x3130, 0x318F)]),
    ("th", [(0x0E00, 0x0E7F)]),
    ("han", [(0x4E00, 0x9FFF), (0x3400, 0x4DBF), (0x3000, 0x303F), (0xFF00, 0xFFEF)]),
    ("other", [(0x0590, 0x08FF), (0x0900, 0x0DFF), (0x0E80, 0x0FFF), (0x1780, 0x17FF), (0x1800, 0x18AF)]),
]
_FONT_PATH_CACHE = {}


def detect_script(text: str) -> str:
    counts = {}
    for ch in str(text or ""):
        cp = ord(ch)
        if cp < 0x0250:
            continue
        for name, ranges in _SCRIPT_RANGES:
            if any(lo <= cp <= hi for lo, hi in ranges):
                counts[name] = counts.get(name, 0) + 1
                break
    if not counts:
        return "latin"
    # kana in a line means Japanese even when it also contains kanji
    for name in ("my", "ja", "ko", "th"):
        if name in counts:
            return name
    return max(counts, key=counts.get)


def pick_font_path_for_text(text: str, lang_hint: str, default_path: str) -> str:
    script = detect_script(text)
    if script == "latin":
        return default_path
    hint = (lang_hint or "my").lower()
    if script == "han":
        script = "zh" if ("zh" in hint or "cn" in hint or "tw" in hint) else ("ko" if "ko" in hint else "ja")
    if script == "other":
        script = "universal"
    key = script
    if key not in _FONT_PATH_CACHE:
        if script == "my":
            path = resolve_font_path("my")
        elif script == "universal":
            path = resolve_font_path("xx-universal")
            # prefer a font with broad coverage
            for p in ("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", "/Library/Fonts/Arial Unicode.ttf",
                      "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "C:/Windows/Fonts/arialuni.ttf"):
                if os.path.exists(p):
                    path = p
                    break
        else:
            path = resolve_font_path(script)
        _FONT_PATH_CACHE[key] = path or default_path
    return _FONT_PATH_CACHE[key]



# ============================================================
# LETTER SPACING (keeps Myanmar / Thai / Indic clusters together)
# ============================================================

import unicodedata


def _text_clusters(text):
    """Split into drawable clusters: a base character plus its combining marks / stacked consonants."""

    clusters = []

    for ch in str(text or ""):

        attach = (
            clusters
            and (
                unicodedata.category(ch).startswith("M")
                or clusters[-1][-1:] == "\u1039"
                or ch in ("\u200d", "\u200c")
            )
        )

        if attach:
            clusters[-1] += ch
        else:
            clusters.append(ch)

    return clusters


def spaced_text_width(draw, text, font, letter_spacing):

    if not text:
        return 0

    if not letter_spacing:
        box = draw.textbbox((0, 0), text, font=font)
        return box[2] - box[0]

    parts = _text_clusters(text)

    return int(
        sum(font.getlength(p) for p in parts)
        + letter_spacing * max(0, len(parts) - 1)
    )


def draw_spaced(draw, xy, text, letter_spacing, **kwargs):

    if not letter_spacing:
        draw.text(xy, text, **kwargs)
        return

    x, y = xy
    font = kwargs.get("font")

    for part in _text_clusters(text):
        draw.text((x, y), part, **kwargs)
        x += font.getlength(part) + letter_spacing



# ============================================================
# BACKGROUND MUSIC
# ============================================================

def resolve_bgm_path():

    candidates = [
        BASE_DIR / "assets" / "dhamma_bgm.mp3",
        BASE_DIR / "assets" / "dhamma_bgm.mp3.mp3",
        BASE_DIR / "dhamma_bgm.mp3",
    ]

    for candidate in candidates:
        if candidate.exists():
            return str(candidate.resolve())

    return ""


# ============================================================
# IMAGE INDEXING
# ============================================================

def scan_and_index_images(media_files, progress_cb=None):

    cache_file = CACHE_DIR / "clip_embeddings_cache.pt"

    current_valid_paths = sorted(
        [
            path
            for path in media_files
            if path.suffix.lower() in [
                ".jpg", ".jpeg", ".png", ".webp"
            ]
        ],
        key=lambda path: path.name.lower()
    )

    if not current_valid_paths:
        return [], None

    if not clip_model_ready():
        # Model not downloaded yet: caller falls back to even spacing.
        return current_valid_paths, None

    cached_dict = {}

    if cache_file.exists():
        try:
            cached_dict = torch.load(
                cache_file,
                weights_only=False,
                map_location="cpu"
            )

            if not isinstance(cached_dict, dict):
                cached_dict = {}

        except Exception:
            cached_dict = {}

    new_paths = [
        path
        for path in current_valid_paths
        if str(path.resolve()) not in cached_dict
    ]

    if new_paths:

        if progress_cb:
            progress_cb(
                f"AI scanning {len(new_paths)} media files...",
                25
            )

        model = get_clip_model()

        new_images = []
        processable = []

        for path in new_paths:
            try:
                img = Image.open(path).convert("RGB")

                img.thumbnail(
                    (320, 320),
                    Image.Resampling.BILINEAR
                )

                new_images.append(img)
                processable.append(path)

            except Exception:
                continue

        if new_images:

            with torch.no_grad():
                new_embeddings = model.encode(
                    new_images,
                    batch_size=32,
                    convert_to_tensor=True,
                    show_progress_bar=False
                )

            for path, embedding in zip(
                processable,
                new_embeddings
            ):
                cached_dict[str(path.resolve())] = embedding.cpu()

            try:
                torch.save(cached_dict, cache_file)
            except Exception:
                pass

    final_paths = []
    final_embeddings_list = []

    for path in current_valid_paths:

        key = str(path.resolve())

        if key in cached_dict:
            final_paths.append(path)
            final_embeddings_list.append(cached_dict[key])

    if not final_embeddings_list:
        return final_paths, None

    return final_paths, torch.stack(final_embeddings_list)


# ============================================================
# HYBRID IMAGE MATCHING
# ============================================================

def spread_images(valid_paths, count):
    """Spread images evenly across the timeline in filename order."""

    if not valid_paths or count <= 0:
        return []

    n = len(valid_paths)

    return [
        valid_paths[min(n - 1, i * n // count)]
        for i in range(count)
    ]


def batch_match_images_hybrid(
    clip_queries,
    valid_paths,
    image_embeddings,
    top_k=5,
    penalty_weight=0.35
):

    if not valid_paths:
        return [Path() for _ in clip_queries]

    if image_embeddings is None:
        return spread_images(valid_paths, len(clip_queries))

    model = get_clip_model()

    clean_queries = [
        str(query).strip() or "dhamma temple monks nature"
        for query in clip_queries
    ]

    with torch.no_grad():
        # Image embeddings are cached on CPU; keep both tensors on the same
        # device before calculating cosine similarity.
        text_embeddings = model.encode(
            clean_queries,
            batch_size=32,
            convert_to_tensor=True
        ).cpu()

        cos_matrix = util.cos_sim(
            text_embeddings,
            image_embeddings.cpu()
        )

    matched_results = []
    usage_counts = Counter()

    total_imgs = len(valid_paths)

    for row in cos_matrix:

        scores = row.tolist()

        unused = [
            i
            for i in range(total_imgs)
            if usage_counts[i] == 0
        ]

        candidates = (
            unused
            if unused
            else list(range(total_imgs))
        )

        best_idx = max(
            candidates,
            key=lambda i: (
                scores[i]
                - (
                    usage_counts[i]
                    * max(penalty_weight, 0.35)
                )
            )
        )

        usage_counts[best_idx] += 1
        matched_results.append(valid_paths[best_idx])

    return matched_results


# ============================================================
# HTML CAPTION PARSING
# ============================================================

def parse_html_tokens(html_content: str):

    raw = html.unescape(
        str(html_content or "")
    ).strip()

    raw = re.sub(
        r'<div><br\s*/?></div>',
        '\n',
        raw,
        flags=re.I
    )

    raw = re.sub(
        r'<div>',
        '\n',
        raw,
        flags=re.I
    )

    raw = re.sub(
        r'</div>',
        '',
        raw,
        flags=re.I
    )

    raw = re.sub(
        r'<br\s*/?>',
        '\n',
        raw,
        flags=re.I
    )

    raw = re.sub(
        r'<p\s*[^>]*>',
        '\n',
        raw,
        flags=re.I
    )

    raw = re.sub(
        r'</p>',
        '',
        raw,
        flags=re.I
    )

    # A whole-segment style wrapper (data-seg) opens on the first line and closes on the last;
    # give every line its own copy so each wrapped line gets its own box / outline.
    seg = re.match(
        r'^\s*<span\b([^>]*?)\bdata-seg=["\']1["\']([^>]*)>(.*)</span>\s*$',
        raw,
        flags=re.S | re.I
    )

    if seg:

        attrs = (seg.group(1) + seg.group(2)).strip()

        raw = "\n".join(
            f'<span {attrs} data-seg="1">{piece}</span>'
            for piece in seg.group(3).split("\n")
            if piece.strip()
        )

    raw_lines = raw.split("\n")
    parsed_lines = []

    for line in raw_lines:

        line_str = line.strip()

        if not line_str:
            continue

        is_box = (
            'data-style="box"' in line_str
            or "data-bg=" in line_str
            or "background-color:" in line_str
        )

        if is_box:

            bg_match = re.search(
                r'data-bg=["\']([^"\']+)["\']',
                line_str
            )

            if not bg_match:
                bg_match = re.search(
                    r'background-color:\s*([^;"]+)',
                    line_str
                )

            bc_match = re.search(
                r'data-bc=["\']([^"\']+)["\']',
                line_str
            )

            if not bc_match:
                bc_match = re.search(
                    r'border(?:-color)?:\s*(?:2px\s+solid\s+)?([^;"]+)',
                    line_str
                )

            bg = (
                bg_match.group(1).strip()
                if bg_match
                else "#8c4e12"
            )

            bc = (
                bc_match.group(1).strip()
                if bc_match
                else "#ffffff"
            )

            clean_txt = re.sub(
                r'<[^>]+>',
                '',
                line_str
            ).strip()

            if clean_txt:
                parsed_lines.append({
                    "text": clean_txt,
                    "style": "box",
                    "bg": bg,
                    "bc": bc,
                    "seg": "data-seg=" in line_str
                })
                continue

        is_outline = (
            'data-style="outline"' in line_str
            or "data-c=" in line_str
        )

        if is_outline:

            color_match = re.search(
                r'data-c=["\']([^"\']+)["\']',
                line_str
            )

            color = (
                color_match.group(1).strip()
                if color_match
                else "#000000"
            )

            clean_txt = re.sub(
                r'<[^>]+>',
                '',
                line_str
            ).strip()

            if clean_txt:
                parsed_lines.append({
                    "text": clean_txt,
                    "style": "outline",
                    "outline_color": color
                })
                continue

        clean_txt = re.sub(
            r'<[^>]+>',
            '',
            line_str
        ).strip()

        if clean_txt:
            parsed_lines.append({
                "text": clean_txt,
                "style": "normal"
            })

    return parsed_lines


# ============================================================
# CAPTION WRAPPING
# ============================================================

def wrap_caption_items(
    parsed_lines,
    draw,
    font,
    max_width,
    letter_spacing=0
):

    wrapped = []
    cur = [None]

    def text_width(value):

        if not value:
            return 0

        return spaced_text_width(
            draw,
            value,
            cur[0],
            letter_spacing
        )

    def split_piece(piece):

        piece = str(piece or "").strip()

        if not piece:
            return []

        if text_width(piece) <= max_width:
            return [piece]

        words = piece.split()

        if len(words) > 1:

            lines = []
            current = ""

            for word in words:

                candidate = (
                    word
                    if not current
                    else current + " " + word
                )

                if text_width(candidate) <= max_width:
                    current = candidate

                else:

                    if current:
                        lines.append(current)

                    if text_width(word) > max_width:

                        chunk = ""

                        for char in word:

                            test = chunk + char

                            if (
                                chunk
                                and text_width(test) > max_width
                            ):
                                lines.append(chunk)
                                chunk = char

                            else:
                                chunk = test

                        current = chunk

                    else:
                        current = word

            if current:
                lines.append(current)

            return lines

        lines = []
        current = ""

        for char in piece:

            candidate = current + char

            if (
                current
                and text_width(candidate) > max_width
            ):
                lines.append(current)
                current = char

            else:
                current = candidate

        if current:
            lines.append(current)

        return lines

    for item in parsed_lines:

        original = str(item.get("text", ""))

        for explicit_line in original.splitlines() or [original]:

            cur[0] = font(explicit_line) if callable(font) else font

            parts = split_piece(explicit_line)

            for part in parts:

                new_item = dict(item)
                new_item["text"] = part
                new_item["font"] = cur[0]

                wrapped.append(new_item)

    return wrapped


# ============================================================
# VIDEO FRAME RENDERING
# ============================================================

def _strip_white_border_background(img):
    """
    Make near-white pixels that connect to the image corners transparent.

    Fixes logos whose "transparent" corners are really opaque (or almost
    opaque) white. White that is enclosed by the artwork is left alone.
    """

    import numpy as np

    w, h = img.size
    arr = np.asarray(img, dtype=np.uint8)

    near_white = (
        (arr[..., 0] >= 235)
        & (arr[..., 1] >= 235)
        & (arr[..., 2] >= 235)
        & (arr[..., 3] >= 40)
    )

    if not near_white.any():
        return img

    # Flood fill from the four corners through near-white pixels
    # (numpy dilation; avoids relying on ImageDraw.floodfill behaviour).
    bg = np.zeros_like(near_white)

    for cy, cx in ((0, 0), (0, w - 1), (h - 1, 0), (h - 1, w - 1)):
        if near_white[cy, cx]:
            bg[cy, cx] = True

    if not bg.any():
        return img

    for _ in range(max(w, h)):

        grown = bg.copy()
        grown[1:, :] |= bg[:-1, :]
        grown[:-1, :] |= bg[1:, :]
        grown[:, 1:] |= bg[:, :-1]
        grown[:, :-1] |= bg[:, 1:]
        grown &= near_white

        if (grown == bg).all():
            break

        bg = grown

    out = arr.copy()
    out[bg, 3] = 0

    return Image.fromarray(out, "RGBA")


def clean_logo_edges(logo_img):
    """
    Remove the white/light halo around transparent logos.

    Many exported PNGs keep white RGB under their anti-aliased edge pixels
    (white matte). After compositing, that shows as light corners on
    rounded-square logos. Re-colour every non-solid pixel from the nearest
    solid pixel and tighten the faint alpha fringe.
    """

    try:
        import numpy as np

        logo_img = _strip_white_border_background(logo_img.convert("RGBA"))

        arr = np.asarray(logo_img.convert("RGBA"), dtype=np.float32)
        rgb = arr[..., :3].copy()
        alpha = arr[..., 3]

        if alpha.min() >= 250:
            return logo_img  # fully opaque: nothing to clean

        solid = (alpha >= 250).astype(np.float32)

        if solid.sum() < 16:
            return logo_img

        def blur(a):
            # 3x3 box blur using shifted sums
            p = np.pad(a, [(1, 1), (1, 1)] + [(0, 0)] * (a.ndim - 2))
            out = np.zeros_like(a)
            for dy in range(3):
                for dx in range(3):
                    out += p[dy:dy + a.shape[0], dx:dx + a.shape[1]]
            return out / 9.0

        filled = rgb * solid[..., None]
        weight = solid.copy()

        # Bleed solid colours outward across the semi-transparent fringe.
        for _ in range(4):
            num = blur(filled)
            den = blur(weight)
            grow = (weight < 1.0) & (den > 1e-4)
            new_rgb = num / np.maximum(den, 1e-4)[..., None]
            filled[grow] = new_rgb[grow]
            weight[grow] = 1.0

        out_rgb = np.where(solid[..., None] > 0, rgb, filled)

        # Squash the faint fringe so near-transparent pixels vanish.
        a_norm = alpha / 255.0
        new_alpha = np.clip((a_norm ** 2.0) * 255.0, 0, 255)
        new_alpha = np.where(alpha >= 250, alpha, new_alpha)

        out = np.dstack([out_rgb, new_alpha]).clip(0, 255).astype(np.uint8)

        return Image.fromarray(out, "RGBA")

    except Exception:
        return logo_img


_BASE_CACHE = {}
_BASE_CACHE_LOCK = threading.Lock()


def _place_image(orig, box_w, box_h, zoom, fx, fy, mode):
    """Crop `orig` to box_w x box_h. mode "cover" fills the box, "width" fits the width.
    zoom >= 1 enlarges, fx/fy (0..1, 0.5 = centre) pick which part stays visible."""

    zoom = max(1.0, float(zoom or 1.0))
    fx = min(1.0, max(0.0, float(0.5 if fx is None else fx)))
    fy = min(1.0, max(0.0, float(0.5 if fy is None else fy)))

    if mode == "width":
        scale = (box_w / orig.width) * zoom
    else:
        scale = max(box_w / orig.width, box_h / orig.height) * zoom

    new_w = max(box_w, int(round(orig.width * scale)))
    new_h = max(box_h, int(round(orig.height * scale)))

    resized = orig.resize((new_w, new_h), Image.Resampling.BILINEAR)

    left = int(round((new_w - box_w) * fx))
    top = int(round((new_h - box_h) * fy))

    return resized.crop((left, top, left + box_w, top + box_h))


def _compose_base_frame(
    bg_path,
    width,
    height,
    opacity_pct,
    logo_path,
    is_mobile,
    logo_dx,
    logo_dy,
    logo_size,
    img_x=0.5,
    img_y=0.5,
    img_zoom=1.0
):
    try:

        orig = Image.open(bg_path).convert("RGB")

        if is_mobile:

            base_canvas = _place_image(
                orig, width, height, img_zoom, img_x, img_y, "cover"
            ).filter(
                ImageFilter.BoxBlur(radius=18)
            )

            fg_h = min(
                int(height * 0.52),
                int(orig.height * (width / orig.width))
            )

            fg = _place_image(
                orig, width, fg_h, img_zoom, img_x, img_y, "width"
            )

            base_canvas.paste(
                fg,
                (0, (height - fg_h) // 2)
            )

        else:

            base_canvas = _place_image(
                orig, width, height, img_zoom, img_x, img_y, "cover"
            )

    except Exception:

        base_canvas = Image.new(
            "RGB",
            (width, height),
            (20, 20, 25)
        )

    frame = base_canvas.convert("RGBA")

    dimmer = Image.new(
        "RGBA",
        (width, height),
        (0, 0, 0, int(255 * (opacity_pct / 100.0)))
    )

    frame = Image.alpha_composite(
        frame,
        dimmer
    )

    if logo_path and os.path.exists(logo_path):

        try:

            logo_img = clean_logo_edges(
                Image.open(
                    logo_path
                ).convert("RGBA")
            )

            logo_px = max(8, int(height * float(logo_size or 0.08)))

            logo_img.thumbnail(
                (logo_px, logo_px),
                Image.Resampling.LANCZOS
            )

            margin_x = 0.032 if is_mobile else 0.03
            margin_y = 0.018 if is_mobile else 0.028

            pos_x = int(
                width
                - logo_img.width
                - margin_x * width
                + float(logo_dx) * width
            )

            pos_y = int(
                margin_y * height
                + float(logo_dy) * height
            )

            frame.paste(
                logo_img,
                (pos_x, pos_y),
                logo_img
            )

        except Exception:
            pass

    return frame


def _cached_base_frame(
    bg_path,
    width,
    height,
    opacity_pct,
    logo_path,
    is_mobile,
    logo_dx,
    logo_dy,
    logo_size,
    img_x=0.5,
    img_y=0.5,
    img_zoom=1.0
):
    """Background + dim + logo is identical for every caption on the same image, so build it once."""

    key = (
        str(bg_path), width, height, opacity_pct,
        str(logo_path), bool(is_mobile),
        round(float(logo_dx), 5), round(float(logo_dy), 5), round(float(logo_size), 5),
        round(float(img_x), 4), round(float(img_y), 4), round(float(img_zoom), 3)
    )

    with _BASE_CACHE_LOCK:
        cached = _BASE_CACHE.get(key)

    if cached is None:
        cached = _compose_base_frame(
            bg_path, width, height, opacity_pct, logo_path,
            is_mobile, logo_dx, logo_dy, logo_size,
            img_x, img_y, img_zoom
        )
        with _BASE_CACHE_LOCK:
            if len(_BASE_CACHE) >= 10:
                _BASE_CACHE.pop(next(iter(_BASE_CACHE)))
            _BASE_CACHE[key] = cached

    return cached.copy()


def build_final_segment_frame(
    bg_path,
    width,
    height,
    parsed_lines,
    font_path,
    font_size,
    line_spacing,
    opacity_pct,
    logo_path,
    is_mobile=False,
    offset_x=0,
    offset_y=0,
    logo_dx=0.0,
    logo_dy=0.0,
    logo_size=0.08,
    lang_hint="my",
    letter_spacing=0,
    img_x=0.5,
    img_y=0.5,
    img_zoom=1.0,
    align_h="center",
    align_v="middle"
):

    frame = _cached_base_frame(
        bg_path,
        width,
        height,
        opacity_pct,
        logo_path,
        is_mobile,
        logo_dx,
        logo_dy,
        logo_size,
        img_x,
        img_y,
        img_zoom
    )

    draw = ImageDraw.Draw(frame)

    try:
        font = load_caption_font(
            font_path,
            font_size
        )

    except Exception as exc:

        warnings.warn(
            f"Could not load caption font: {exc}"
        )

        font = ImageFont.load_default()

    max_text_width = int(
        width * (0.86 if is_mobile else 0.88)
    )

    font_cache = {}

    def font_for(text):

        path = pick_font_path_for_text(text, lang_hint, font_path)

        if path not in font_cache:
            try:
                font_cache[path] = load_caption_font(path, font_size)
            except Exception:
                font_cache[path] = font

        return font_cache[path]

    parsed_lines = wrap_caption_items(
        parsed_lines,
        draw,
        font_for,
        max_text_width,
        letter_spacing
    )

    measured = []
    total_text_height = 0

    for item in parsed_lines:

        txt = item["text"]

        bbox = draw.textbbox(
            (0, 0),
            txt,
            font=item.get("font", font)
        )

        w = spaced_text_width(
            draw,
            txt,
            item.get("font", font),
            letter_spacing
        )
        h = bbox[3] - bbox[1]

        measured.append({
            "item": item,
            "w": w,
            "h": h
        })

        total_text_height += h + line_spacing

    if total_text_height > 0:
        total_text_height -= line_spacing

    margin_y = int(height * 0.06)

    if align_v == "top":
        base_y = margin_y
    elif align_v == "bottom":
        base_y = height - margin_y - total_text_height
    else:
        base_y = (height - total_text_height) // 2

    curr_y = base_y + int(offset_y)

    region_left = (width - max_text_width) // 2

    def line_x(line_w):
        """Left edge of a line: start / middle / end of the text area."""

        if align_h == "start":
            return region_left + int(offset_x)

        if align_h == "end":
            return region_left + max_text_width - line_w + int(offset_x)

        return ((width - line_w) // 2) + int(offset_x)

    # A whole-segment box is ONE rectangle around every line of the caption.
    seg_rect = None
    seg_fill = seg_edge = None
    scan_y = curr_y
    pad_x = int(font_size * 0.38)
    pad_y = int(font_size * 0.16)

    for m in measured:

        it = m["item"]

        if it.get("style") == "box" and it.get("seg"):

            x0 = line_x(m["w"])

            r = [
                x0 - pad_x,
                scan_y - pad_y,
                x0 + m["w"] + pad_x,
                scan_y + m["h"] + pad_y
            ]

            seg_rect = (
                r if seg_rect is None
                else [
                    min(seg_rect[0], r[0]),
                    min(seg_rect[1], r[1]),
                    max(seg_rect[2], r[2]),
                    max(seg_rect[3], r[3])
                ]
            )

            seg_fill = it.get("bg", "#8c4e12")
            seg_edge = it.get("bc", "#ffffff")

        scan_y += m["h"] + line_spacing

    if seg_rect:

        draw.rounded_rectangle(
            seg_rect,
            radius=12,
            fill=seg_fill,
            outline=seg_edge,
            width=3
        )

    for measured_item in measured:

        item = measured_item["item"]

        txt = item["text"]
        w = measured_item["w"]
        h = measured_item["h"]

        curr_x = line_x(w)

        style = item.get(
            "style",
            "normal"
        )

        if style == "box":

            bg_color = item.get(
                "bg",
                "#8c4e12"
            )

            bc_color = item.get(
                "bc",
                "#ffffff"
            )

            if not item.get("seg"):

                rect_box = [
                    curr_x - pad_x,
                    curr_y - pad_y,
                    curr_x + w + pad_x,
                    curr_y + h + pad_y
                ]

                draw.rounded_rectangle(
                    rect_box,
                    radius=10,
                    fill=bg_color,
                    outline=bc_color,
                    width=3
                )

            draw_spaced(
                draw,
                (curr_x, curr_y),
                txt,
                letter_spacing,
                font=item.get("font", font),
                fill=(255, 255, 255, 255),
                stroke_width=2,
                stroke_fill=(0, 0, 0, 255)
            )

        elif style == "outline":

            outline_color = item.get(
                "outline_color",
                "#000000"
            )

            draw_spaced(
                draw,
                (curr_x, curr_y),
                txt,
                letter_spacing,
                font=item.get("font", font),
                fill=(255, 255, 255, 255),
                stroke_width=3,
                stroke_fill=outline_color
            )

        else:

            draw_spaced(
                draw,
                (curr_x, curr_y),
                txt,
                letter_spacing,
                font=item.get("font", font),
                fill=(255, 255, 255, 255),
                stroke_width=3,
                stroke_fill=(0, 0, 0, 255)
            )

        curr_y += h + line_spacing

    return frame.convert("RGB")


# ============================================================
# VIDEO RESOLUTION
# ============================================================

def get_resolution(
    format_type: str,
    quality: str = "720p"
):

    is_mobile = format_type == "mobile"

    if quality == "1080p":

        return (
            (1080, 1920)
            if is_mobile
            else (1920, 1080)
        )

    elif quality == "540p":

        return (
            (540, 960)
            if is_mobile
            else (960, 540)
        )

    else:

        return (
            (720, 1280)
            if is_mobile
            else (1280, 720)
        )


# ============================================================
# RENDER ALL CLIPS
# ============================================================

TRANSITION_FPS = 25


ANIM_PCT_START = 22
ANIM_PCT_END = 92


def encode_transition_clips(
    jobs,
    temp_dir,
    width,
    height,
    transition,
    progress_cb
):
    """
    Turn each baked caption frame into a short animated mp4 clip.

    fade: dip-to-black fade out/in at every scene change.
    zoom: slow push-in (Ken Burns) plus fade.
    """

    fps = TRANSITION_FPS
    done = {"n": 0}
    total = len(jobs)
    lock = threading.Lock()
    frames_done = {}
    total_frames = max(1, sum(j[2] for j in jobs))
    last_emit = {"t": 0.0}

    def report(idx, frames):
        """Aggregate real frame counts from every running ffmpeg into one smooth percentage."""

        import time

        with lock:

            frames_done[idx] = frames
            now = time.monotonic()

            if now - last_emit["t"] < 0.25 and frames < total_frames:
                return

            last_emit["t"] = now
            frac = min(1.0, sum(frames_done.values()) / total_frames)
            finished = done["n"]

        progress_cb(
            f"Animating scenes {finished}/{total} ({int(frac * 100)}%)...",
            ANIM_PCT_START + int(frac * (ANIM_PCT_END - ANIM_PCT_START))
        )

    # Upscale before zoompan so the slow zoom stays smooth, not jittery.
    pre = 2.0 if width * height <= 1280 * 720 else 1.3
    pre_w = int(width * pre) // 2 * 2
    pre_h = int(height * pre) // 2 * 2

    def encode(job):

        idx, seg_file, n_frames = job

        out = temp_dir / f"clip_{idx}.mp4"

        dur = n_frames / fps
        fade_d = max(0.08, min(0.35, dur * 0.3))
        fade_out_start = max(0.0, dur - fade_d)

        fades = (
            f"fade=t=in:st=0:d={fade_d:.3f},"
            f"fade=t=out:st={fade_out_start:.3f}:d={fade_d:.3f}"
        )

        if transition != "fade" and transition != "none":

            # Sub-pixel camera move. zoompan crops on whole pixels, which makes slow
            # zooms/pans step and shake; perspective interpolates between pixels (cubic).
            N = max(1, n_frames)
            p = f"(on/{N})"
            if transition == "zoom":
                z = f"(1+0.06*{p})"
                left, top = f"(W-W/{z})/2", f"(H-H/{z})/2"
                cw, ch = f"(W/{z})", f"(H/{z})"
            elif transition == "zoom-out":
                z = f"(1.06-0.06*{p})"
                left, top = f"(W-W/{z})/2", f"(H-H/{z})/2"
                cw, ch = f"(W/{z})", f"(H/{z})"
            else:
                z = "1.08"
                cw, ch = f"(W/{z})", f"(H/{z})"
                left, top = f"(W-{cw})/2", f"(H-{ch})/2"
                if transition == "pan-left":
                    left = f"(W-{cw})*(1-{p})"
                elif transition == "pan-right":
                    left = f"(W-{cw})*{p}"
                elif transition == "drift-up":
                    top = f"(H-{ch})*(1-{p})"
                else:
                    top = f"(H-{ch})*{p}"

            vf = (
                f"perspective="
                f"x0='{left}':y0='{top}':"
                f"x1='({left})+{cw}':y1='{top}':"
                f"x2='{left}':y2='({top})+{ch}':"
                f"x3='({left})+{cw}':y3='({top})+{ch}':"
                f"eval=frame:interpolation=cubic,"
                f"{fades},format=yuv420p"
            )

            in_args = [
                "-loop", "1",
                "-framerate", str(fps),
                "-i", str(seg_file)
            ]

        else:

            vf = f"{fades},format=yuv420p"

            in_args = [
                "-loop", "1",
                "-framerate", str(fps),
                "-i", str(seg_file)
            ]

        cmd = [
            FFMPEG_BIN,
            "-y",
            "-nostdin",
            "-hide_banner",
            "-loglevel", "error",
            *in_args,
            "-vf", vf,
            "-frames:v", str(n_frames),
            "-r", str(fps),
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "20",
            "-pix_fmt", "yuv420p",
            "-an",
            str(out)
        ]

        cmd[1:1] = ["-progress", "pipe:1", "-nostats"]

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        log = []

        for line in proc.stdout:

            line = line.strip()

            if line.startswith("frame="):

                try:
                    report(idx, int(line.split("=", 1)[1]))
                except ValueError:
                    pass

            elif line and "=" not in line:
                log.append(line)

        proc.wait()

        if proc.returncode != 0:
            raise RuntimeError(
                f"Transition clip {idx} failed: {' '.join(log)[-400:]}"
            )

        report(idx, n_frames)

        with lock:
            done["n"] += 1

        return out

    with ThreadPoolExecutor(
        max_workers=max(2, min(6, os.cpu_count() or 2))
    ) as pool:

        # Start the longest scenes first so one big scene never becomes a long idle tail.
        order = sorted(jobs, key=lambda j: -j[2])
        results = dict(zip((j[0] for j in order), pool.map(encode, order)))

        return [results[j[0]] for j in jobs]


def render_all_clips(
    df,
    media_dir,
    audio_path,
    output_file,
    logo_path,
    cfg,
    progress_cb
):

    temp_dir = Path(
        tempfile.mkdtemp(prefix="dhamma_opt_")
    )

    try:

        format_type = cfg.get(
            "format",
            "landscape"
        )

        quality = cfg.get(
            "quality",
            "720p"
        )

        is_mobile = format_type == "mobile"

        target_lang = str(
            cfg.get("target_lang", "my")
        ).lower().strip()

        width, height = get_resolution(
            format_type,
            quality
        )

        base_font_sz = int(
            cfg.get(
                "font_size",
                38 if is_mobile else 44
            )
        )

        scale_ratio = (
            height
            / (1920 if is_mobile else 1080)
        )

        font_size = max(
            18,
            int(base_font_sz * scale_ratio)
        )

        line_spacing = max(
            6,
            int(
                int(cfg.get("line_spacing", 26))
                * scale_ratio
            )
        )

        opacity = int(
            cfg.get("opacity", 45)
        )

        transition = str(
            cfg.get("transition", "fade")
        ).lower().strip()

        if transition not in ("none", "fade", "zoom", "zoom-out", "pan-left", "pan-right", "drift-up", "drift-down"):
            transition = "fade"

        scene_jobs = []
        timeline_acc = 0.0

        font_path = resolve_font_path(
            target_lang=target_lang
        )

        search_dirs = [
            Path(media_dir),
            APP_DATA_DIR / "uploads" / "images",
            BASE_DIR / "images",
            BASE_DIR
        ]

        fallback_images = []

        for directory in search_dirs:

            if directory.exists():

                fallback_images += (
                    list(directory.glob("*.jpg"))
                    + list(directory.glob("*.png"))
                )

        default_fallback = (
            fallback_images[0]
            if fallback_images
            else Path("empty.jpg")
        )

        progress_cb(
            f"Synthesizing [{target_lang.upper()}] scenes...",
            15
        )

        total_rows = len(df)

        concat_txt = temp_dir / "timeline_concat.txt"

        # ---- plan every scene first (cheap, sequential: keeps the timeline math exact) ----
        plans = []

        for idx, row in df.iterrows():

            matched_img = row.get("matched_img", "")

            img_name = (
                Path(matched_img).name
                if matched_img
                else ""
            )

            source_p = None

            for directory in search_dirs:

                if (directory / img_name).exists():

                    source_p = directory / img_name
                    break

            if not source_p:
                source_p = default_fallback

            dur = max(
                0.4,
                float(row["end_time"])
                - float(row["start_time"])
            )

            n_frames = None

            if transition != "none":

                # Frame counts come from cumulative time so rounding
                # never drifts away from the narration audio.
                n_frames = max(
                    2,
                    round((timeline_acc + dur) * TRANSITION_FPS)
                    - round(timeline_acc * TRANSITION_FPS)
                )

                timeline_acc += dur

            def _num(key, default):
                try:
                    v = row.get(key, default)
                    return default if v is None or v != v else float(v)
                except Exception:
                    return default

            plans.append({
                "idx": idx,
                "img_x": _num("img_x", 0.5),
                "img_y": _num("img_y", 0.5),
                "img_zoom": _num("img_zoom", 1.0),
                "source": source_p,
                "dur": dur,
                "n_frames": n_frames,
                "tokens": parse_html_tokens(str(row.get("caption", ""))),
                "seg_file": temp_dir / f"seg_{idx}.jpg",
            })

        # ---- build the caption frames in parallel (PIL releases the GIL for the heavy parts) ----
        built = {"n": 0}
        built_lock = threading.Lock()

        def build_scene(plan):

            frame_img = build_final_segment_frame(
                plan["source"],
                width,
                height,
                plan["tokens"],
                font_path,
                font_size,
                line_spacing,
                opacity,
                logo_path,
                is_mobile=is_mobile,
                offset_x=float(cfg.get("text_dx", 0) or 0) * width,
                offset_y=float(cfg.get("text_dy", 0) or 0) * height,
                logo_dx=float(cfg.get("logo_dx", 0) or 0),
                logo_dy=float(cfg.get("logo_dy", 0) or 0),
                logo_size=float(cfg.get("logo_size", 0.08) or 0.08),
                lang_hint=target_lang,
                letter_spacing=float(cfg.get("letter_spacing", 0) or 0) * scale_ratio,
                img_x=plan["img_x"],
                img_y=plan["img_y"],
                img_zoom=plan["img_zoom"],
                align_h=str(cfg.get("text_align_h", "center")),
                align_v=str(cfg.get("text_align_v", "middle"))
            )

            frame_img.save(
                plan["seg_file"],
                "JPEG",
                quality=92
            )

            with built_lock:

                built["n"] += 1
                n = built["n"]

            progress_cb(
                f"Synthesized {n}/{total_rows} scenes ({target_lang.upper()})...",
                15 + int((n / max(1, total_rows)) * 7)
            )

        workers = max(2, min(6, (os.cpu_count() or 2)))

        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(build_scene, plans))

        with open(
            concat_txt,
            "w",
            encoding="utf-8"
        ) as f_out:

            for plan in plans:

                seg_file = plan["seg_file"]

                if transition == "none":

                    f_out.write(
                        f"file '{str(seg_file.resolve()).replace(chr(92), '/')}'\n"
                    )

                    f_out.write(
                        f"duration {plan['dur']:.3f}\n"
                    )

                else:

                    scene_jobs.append(
                        (plan["idx"], seg_file, plan["n_frames"])
                    )

            if total_rows > 0 and transition == "none":

                last_seg = (
                    temp_dir
                    / f"seg_{total_rows - 1}.jpg"
                )

                f_out.write(
                    f"file '{str(last_seg.resolve()).replace(chr(92), '/')}'\n"
                )

        if scene_jobs:

            progress_cb(
                f"Animating {len(scene_jobs)} scene transitions...",
                22
            )

            clip_files = encode_transition_clips(
                scene_jobs,
                temp_dir,
                width,
                height,
                transition,
                progress_cb
            )

            with open(
                concat_txt,
                "w",
                encoding="utf-8"
            ) as f_out:

                for clip in clip_files:

                    f_out.write(
                        f"file '{str(clip.resolve()).replace(chr(92), '/')}'\n"
                    )

        total_duration = max(
            1.0,
            float(df["end_time"].max())
            if len(df)
            else 1.0
        )

        first_clip_duration = max(
            0.5,
            float(df.iloc[0]["end_time"])
            if len(df)
            else total_duration
        )

        enable_bgm_cfg = bool(
            cfg.get("enable_bgm", True)
        )

        bgm_path = resolve_bgm_path()

        has_intro_bgm = (
            enable_bgm_cfg
            and bgm_path
            and os.path.exists(bgm_path)
        )

        input_args = [
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_txt),
            "-i",
            str(audio_path)
        ]

        if has_intro_bgm:

            input_args += [
                "-i",
                str(bgm_path)
            ]

            fade_dur = min(
                1.5,
                first_clip_duration * 0.3
            )

            fade_start = max(
                0.0,
                first_clip_duration - fade_dur
            )

            filter_complex_str = (
                f"[2:a]atrim=0:{first_clip_duration:.2f},"
                f"volume=0.20,"
                f"afade=t=out:st={fade_start:.2f}:d={fade_dur:.2f}[bgm_intro];"
                f"[1:a][bgm_intro]amix=inputs=2:duration=first:dropout_transition=0[a_out]"
            )

            audio_map = "[a_out]"

        else:

            filter_complex_str = ""
            audio_map = "1:a"

        cmd = [
            FFMPEG_BIN,
            "-y",
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            *input_args
        ]

        if filter_complex_str:

            cmd += [
                "-filter_complex",
                filter_complex_str
            ]

        cmd += [
            "-map",
            "0:v",
            "-map",
            audio_map,
            "-t",
            f"{total_duration:.3f}",
            *(
                ["-c:v", "copy"]
                if scene_jobs
                else [
                    "-c:v", "libx264",
                    "-preset", "ultrafast",
                    "-crf", "22",
                    "-pix_fmt", "yuv420p",
                ]
            ),
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-progress",
            "pipe:1",
            "-nostats",
            str(output_file)
        ]

        final_base = ANIM_PCT_END if scene_jobs else 50
        final_span = (99 - ANIM_PCT_END) if scene_jobs else 48

        progress_cb(
            f"Encoding [{target_lang.upper()}] video...",
            final_base
        )

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )

        for line in process.stdout:

            line = line.strip()

            if line.startswith("out_time_us="):

                try:

                    val = int(
                        line.split("=", 1)[1]
                    )

                    elapsed = val / 1_000_000

                    pct = min(
                        99,
                        final_base + int(
                            (elapsed / total_duration) * final_span
                        )
                    )

                    progress_cb(
                        f"Rendering {target_lang.upper()} ({int((elapsed / total_duration) * 100)}%)...",
                        pct
                    )

                except Exception:
                    pass

        process.wait(timeout=300)

        if process.returncode != 0:

            err = process.stderr.read()

            return False, f"FFmpeg Error: {err}"

        progress_cb(
            f"[{target_lang.upper()}] Video ready! Click Download.",
            100
        )

        return True, str(output_file)

    except Exception as exc:

        return False, str(exc)

    finally:

        shutil.rmtree(
            temp_dir,
            ignore_errors=True
        )
