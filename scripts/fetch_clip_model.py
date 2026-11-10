"""Download the CLIP model into vendor/models so it can be bundled offline.

Run with: uv run python scripts/fetch_clip_model.py
"""
from pathlib import Path

from sentence_transformers import SentenceTransformer

dest = Path(__file__).resolve().parent.parent / "vendor" / "models" / "clip-ViT-B-32"
if (dest / "modules.json").exists():
    print(f"CLIP model already present at {dest}")
else:
    dest.parent.mkdir(parents=True, exist_ok=True)
    SentenceTransformer("clip-ViT-B-32").save(str(dest))
    print(f"CLIP model saved to {dest}")
