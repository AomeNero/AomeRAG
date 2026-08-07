"""图片后处理：从 markdown 提取图片 → Pillow 转 PNG → 存 images/ 目录。"""

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
    """按内容哈希名 `image_<sha1(png)[:16]>.png` 保存 PNG 字节；
    内容相同则复用已有文件（同名，不累积）。"""
    name = f"image_{hashlib.sha1(png_bytes).hexdigest()[:16]}.png"
    path = images_dir / name
    if not path.exists():
        path.write_bytes(png_bytes)
    return name


def _save_png(data: bytes, images_dir: Path) -> str | None:
    """用 Pillow 把位图字节转成 PNG 并保存。返回文件名或 None。"""
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
    """用 PowerShell + System.Drawing（Windows 内置）把 EMF/WMF 渲染成 PNG。
    返回内容哈希文件名，失败返回 None。"""
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
    """在 markdown 中找图片，转成 PNG，把链接改写成相对路径。

    链接相对 md 文件所在目录（`md_dir`），所以本地打开 .md 和聊天页
    （根 `/` → `/images/…`）都能解析。默认 `md_dir` = 图片目录的父目录
    （md-data 根）→ 链接形如 `images/<name>`。
    """
    images_dir.mkdir(parents=True, exist_ok=True)
    base = md_dir if md_dir is not None else images_dir.parent
    prefix = os.path.relpath(images_dir, base).replace("\\", "/")

    def _link(name: str | None) -> str | None:
        return f"{prefix}/{name}" if name else None

    # 1. data URI：![alt](data:image/png;base64,XXXX)
    def _repl_data(m: re.Match) -> str:
        alt, b64 = m.group(1), m.group(2)
        rel = _link(_save_png(base64.b64decode(b64), images_dir))
        return f"![{alt}]({rel})" if rel else m.group(0)

    markdown = re.sub(
        r"!\[([^\]]*)\]\(data:image/[^;]+;base64,([A-Za-z0-9+/=\s]+)\)",
        _repl_data,
        markdown,
    )

    # 2. http(s) 链接：![alt](https://...)
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

    # 3. 本地媒体文件（来自 pandoc --extract-media）
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

                    # 3a. markdown 语法：![alt](...image1.png) → ![alt](rel)
                    # （去掉媒体文件名前的任意路径前缀）
                    markdown = re.sub(
                        rf'!\[([^\]]*)\]\([^)]*?{old}\)', rf'![\1]({rel})', markdown
                    )

                    # 3b. HTML <img src="...image1.png" .../> —— pandoc 对指定尺寸的图片
                    # 输出原始 HTML，有时是多行引用块（每个属性独占一行 `> `）；
                    # react-markdown（无 rehype-raw）会转义原始 HTML，所以转成
                    # markdown 图片语法（保留 alt，去掉尺寸）。
                    # (?s) 让点号跨行，但遇到下一个 <img 停止。
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
                    # 转换失败——原引用指向 pandoc 临时路径，清洗后已不存在，
                    # 删除这个失效引用。
                    markdown = re.sub(rf"!\[[^\]]*\]\([^)]*?{old}\)", "", markdown)
                    markdown = re.sub(
                        rf'(?s)<img\b(?:(?!<img\b).)*?src="[^"]*{old}"(?:(?!<img\b).)*?/?>',
                        "",
                        markdown,
                    )
            except Exception:
                pass

    return markdown
