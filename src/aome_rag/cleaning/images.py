"""Image post-processor: extract images from markdown, convert to PNG, rewrite links.

Handles three image sources:
  1. data: URIs (base64-inline images from MarkItDown)
  2. http(s) URLs (remote images, downloaded via requests)
  3. local files from Pandoc --extract-media (walked and converted)

All raster formats are converted to PNG via Pillow; EMF/WMF (Pillow cannot read them) are
rendered via PowerShell + System.Drawing (Windows built-in). Images are saved to images_dir
with a content-hash name. A conversion/download failure keeps the original reference for
remote URLs, but removes it for extracted local media (whose temp path no longer exists).
"""

from __future__ import annotations

import base64
import hashlib
import io
import os
import re
import subprocess
import tempfile
from pathlib import Path

from PIL import Image
import requests

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp", ".emf", ".wmf"}
_EMF_EXTS = {".emf", ".wmf"}


def _save_png_bytes(png_bytes: bytes, images_dir: Path) -> str:
    """Save PNG bytes under a content-hash name `image_<sha1(png)[:16]>.png`;
    reuses an existing file (same content → same name, no accumulation)."""
    name = f"image_{hashlib.sha1(png_bytes).hexdigest()[:16]}.png"
    path = images_dir / name
    if not path.exists():
        path.write_bytes(png_bytes)
    return name


def _save_png(data: bytes, images_dir: Path) -> str | None:
    """Convert raster bytes to PNG via Pillow and save. Returns the filename or None."""
    try:
        img = Image.open(io.BytesIO(data))
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, "PNG")
        return _save_png_bytes(buf.getvalue(), images_dir)
    except Exception:
        return None


def _convert_emf(src: Path, images_dir: Path) -> str | None:
    """Render an EMF/WMF file to PNG via PowerShell + System.Drawing (Windows built-in).
    Returns the content-hash filename, or None on failure."""
    try:
        images_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as td:
            out_png = Path(td) / "out.png"
            script = (
                "Add-Type -AssemblyName System.Drawing; "
                f"$img = [System.Drawing.Image]::FromFile('{src.as_posix()}'); "
                f"$img.Save('{out_png.as_posix()}', [System.Drawing.Imaging.ImageFormat]::Png); "
                "$img.Dispose()"
            )
            r = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True,
                timeout=60,
            )
            if r.returncode != 0 or not out_png.is_file():
                return None
            return _save_png_bytes(out_png.read_bytes(), images_dir)
    except Exception:
        return None


def process_images(
    markdown: str,
    images_dir: Path,
    media_dir: Path | None = None,
    md_dir: Path | None = None,
) -> str:
    """Find images in markdown, convert to PNG, rewrite links to relative paths.

    Links are relative to the md file's directory (`md_dir`), so they resolve both when
    opening the .md locally and from the chat page (root `/` → `/images/…`). Default
    `md_dir` = images dir's parent (md-data root) → links read `images/<name>`.
    """
    images_dir.mkdir(parents=True, exist_ok=True)
    base = md_dir if md_dir is not None else images_dir.parent
    prefix = os.path.relpath(images_dir, base).replace("\\", "/")

    def _link(name: str | None) -> str | None:
        return f"{prefix}/{name}" if name else None

    # 1. data URIs: ![alt](data:image/png;base64,XXXX)
    def _repl_data(m: re.Match) -> str:
        alt, b64 = m.group(1), m.group(2)
        rel = _link(_save_png(base64.b64decode(b64), images_dir))
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
            rel = _link(_save_png(r.content, images_dir))
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
                if img_path.suffix.lower() in _EMF_EXTS:
                    name = _convert_emf(img_path, images_dir)  # PowerShell render
                else:
                    name = _save_png(img_path.read_bytes(), images_dir)
                old = re.escape(img_path.name)

                if name:
                    rel = _link(name)

                    # 3a. markdown syntax: ![alt](...image1.png) → ![alt](rel)
                    # (drop any path prefix before the media filename)
                    markdown = re.sub(
                        rf'!\[([^\]]*)\]\([^)]*?{old}\)', rf'![\1]({rel})', markdown
                    )

                    # 3b. HTML <img src="...image1.png" .../> — pandoc emits raw HTML for
                    # sized images, sometimes as multi-line blockquotes (each attribute on
                    # its own `> ` line); react-markdown (no rehype-raw) would escape raw
                    # HTML, so convert to markdown image syntax (alt preserved, size dropped).
                    # The tempered dot (?s) crosses newlines but stops at the next <img.
                    def _repl_html_img(m: re.Match) -> str:
                        am = re.search(r'alt="([^"]*)"', m.group(0))
                        alt = am.group(1) if am else img_path.stem
                        return f"![{alt}]({rel})"

                    markdown = re.sub(
                        rf'(?s)<img\b(?:(?!<img\b).)*?src="[^"]*{old}"(?:(?!<img\b).)*?/?>',
                        _repl_html_img,
                        markdown,
                    )
                else:
                    # conversion failed — the original reference points at a pandoc temp path
                    # that no longer exists after cleaning, so drop the broken reference.
                    markdown = re.sub(rf"!\[[^\]]*\]\([^)]*?{old}\)", "", markdown)
                    markdown = re.sub(
                        rf'(?s)<img\b(?:(?!<img\b).)*?src="[^"]*{old}"(?:(?!<img\b).)*?/?>',
                        "",
                        markdown,
                    )
            except Exception:
                pass

    return markdown
