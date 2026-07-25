"""Image post-processor: extract images from markdown, convert to PNG, rewrite links.

Handles three image sources:
  1. data: URIs (base64-inline images from MarkItDown)
  2. http(s) URLs (remote images, downloaded via requests)
  3. local files from Pandoc --extract-media (walked and converted)

All images are converted to PNG via Pillow and saved to images_dir with timestamp names.
Pillow-unreadable images (e.g. EMF/WMF) are silently skipped.
"""

from __future__ import annotations

import base64
import io
import re
from datetime import datetime
from pathlib import Path

from PIL import Image
import requests

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp"}


def _save_png(data: bytes, images_dir: Path) -> str | None:
    """Convert bytes to PNG via Pillow, save with timestamp name. Returns relative path."""
    try:
        img = Image.open(io.BytesIO(data))
        ts = datetime.now().strftime("%Y%m%d%H%M%S%f")
        name = f"image_{ts}.png"
        path = images_dir / name
        n = 1
        while path.exists():
            name = f"image_{ts}_{n}.png"
            path = images_dir / name
            n += 1
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")
        img.save(path, "PNG")
        return f"images/{name}"
    except Exception:
        return None


def process_images(
    markdown: str, images_dir: Path, media_dir: Path | None = None
) -> str:
    """Find images in markdown, convert to PNG, rewrite links to relative paths."""
    images_dir.mkdir(parents=True, exist_ok=True)

    # 1. data URIs: ![alt](data:image/png;base64,XXXX)
    def _repl_data(m: re.Match) -> str:
        alt, b64 = m.group(1), m.group(2)
        rel = _save_png(base64.b64decode(b64), images_dir)
        return f"![{alt}]({rel})" if rel else m.group(0)

    markdown = re.sub(
        r"!\[([^\]]*)\]\(data:image/[^;]+;base64,([A-Za-z0-9+/=\s]+)\)",
        _repl_data,
        markdown,
    )

    # 2. http(s) URLs: ![alt](https://...)
    def _repl_http(m: re.Match) -> str:
        alt, url = m.group(1), m.group(2)
        try:
            r = requests.get(url, timeout=15, allow_redirects=True)
            r.raise_for_status()
            rel = _save_png(r.content, images_dir)
            return f"![{alt}]({rel})" if rel else m.group(0)
        except Exception:
            return m.group(0)

    markdown = re.sub(
        r"!\[([^\]]*)\]\((https?://[^)\s]+)\)", _repl_http, markdown
    )

    # 3. local media files (from pandoc --extract-media)
    if media_dir and media_dir.is_dir():
        for img_path in sorted(media_dir.rglob("*")):
            if not img_path.is_file() or img_path.suffix.lower() not in _IMAGE_EXTS:
                continue
            try:
                rel = _save_png(img_path.read_bytes(), images_dir)
                if rel:
                    old = re.escape(img_path.name)
                    markdown = re.sub(
                        rf"(!\[[^\]]*\]\([^)]*?){old}\)", rf"\1{rel})", markdown
                    )
            except Exception:
                pass

    return markdown
