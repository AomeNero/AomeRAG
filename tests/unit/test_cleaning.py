"""Unit tests for cleaning: front-matter + image extraction."""

import base64
import io
import re
from datetime import date

from PIL import Image

from aome_rag.cleaning.frontmatter import build_front_matter
from aome_rag.cleaning.images import process_images


def test_frontmatter_fields() -> None:
    fm = build_front_matter("My Doc")
    assert fm.startswith("---\n")
    assert 'title: "My Doc"' in fm
    assert f'date: "{date.today().isoformat()}"' in fm
    assert 'author: ""' in fm
    assert 'description: ""' in fm
    assert "tags: []" in fm
    assert fm.endswith("---\n\n")


def test_image_data_uri_extracted(tmp_path) -> None:
    images_dir = tmp_path / "images"
    buf = io.BytesIO()
    Image.new("RGB", (2, 2), (255, 0, 0)).save(buf, "PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    md = f"Hello\n\n![red dot](data:image/png;base64,{b64})\n\nWorld"
    result = process_images(md, images_dir)
    assert "data:" not in result
    assert "images/image_" in result
    pngs = list(images_dir.glob("image_*.png"))
    assert len(pngs) == 1


def test_image_name_is_content_hash(tmp_path) -> None:
    """Extracted images must be named image_<sha1[:16]>.png (content hash)."""
    images_dir = tmp_path / "images"
    buf = io.BytesIO()
    Image.new("RGB", (2, 2), (255, 0, 0)).save(buf, "PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    process_images(f"![dot](data:image/png;base64,{b64})", images_dir)
    pngs = list(images_dir.glob("image_*.png"))
    assert len(pngs) == 1
    assert re.fullmatch(r"image_[0-9a-f]{16}\.png", pngs[0].name)


def test_image_name_dedupes_same_content(tmp_path) -> None:
    """Two images with identical content share one content-hash file (no accumulation)."""
    from aome_rag.cleaning import images as img_mod

    images_dir = tmp_path / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    Image.new("RGB", (2, 2), (255, 0, 0)).save(buf, "PNG")
    data = buf.getvalue()
    img_mod._save_png(data, images_dir)
    img_mod._save_png(data, images_dir)

    names = list(images_dir.glob("image_*.png"))
    assert len(names) == 1
    assert re.fullmatch(r"image_[0-9a-f]{16}\.png", names[0].name)


def test_multiline_blockquote_img_converted(tmp_path) -> None:
    """Pandoc GFM emits multi-line blockquote <img> (each attr on its own `> ` line);
    those must also be converted to markdown image syntax."""
    images_dir = tmp_path / "images"
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    buf = io.BytesIO()
    Image.new("RGB", (2, 2), (255, 0, 0)).save(buf, "PNG")
    (media_dir / "image1.png").write_bytes(buf.getvalue())
    md = (
        "> <img\n"
        '> src="C:\\\\Temp\\\\pandoc_media_x\\\\media\\\\image1.png"\n'
        '> style="width:3.9in;height:0.9in" />\n'
    )
    result = process_images(md, images_dir, media_dir=media_dir)
    assert "<img" not in result
    assert "![image1](images/image_" in result
    assert len(list(images_dir.glob("image_*.png"))) == 1


def test_pandoc_html_img_converted_to_markdown(tmp_path) -> None:
    """Pandoc emits <img src=...> HTML for sized docx images; those must be rewritten to
    markdown image syntax (react-markdown without rehype-raw escapes raw HTML)."""
    images_dir = tmp_path / "images"
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    buf = io.BytesIO()
    Image.new("RGB", (2, 2), (255, 0, 0)).save(buf, "PNG")
    (media_dir / "image1.png").write_bytes(buf.getvalue())
    md = '<img src="C:\\\\Temp\\\\pandoc_media_x\\\\media\\\\image1.png" style="width:5.7in;height:3.1in" />'
    result = process_images(md, images_dir, media_dir=media_dir)
    assert "<img" not in result
    assert "![image1](images/image_" in result
    assert len(list(images_dir.glob("image_*.png"))) == 1


def test_image_link_relative_to_md_subdir(tmp_path) -> None:
    """An md inside a subdirectory references the flat images pool with ../images/."""
    images_dir = tmp_path / "images"
    md_dir = tmp_path / "sub"  # raw/sub/file.docx → md/sub/file.md
    buf = io.BytesIO()
    Image.new("RGB", (2, 2), (255, 0, 0)).save(buf, "PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    md = f"![dot](data:image/png;base64,{b64})"
    result = process_images(md, images_dir, md_dir=md_dir)
    assert "../images/image_" in result


def test_emf_media_routed_to_powershell(tmp_path, monkeypatch) -> None:
    """EMF/WMF media files are handled (not skipped) and rewritten to the PNG link."""
    from aome_rag.cleaning import images as img_mod

    images_dir = tmp_path / "images"
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    (media_dir / "image1.emf").write_bytes(b"\x01\x00\x00\x00")  # placeholder EMF bytes
    monkeypatch.setattr(img_mod, "_convert_emf", lambda src, d: "image_0123456789abcdef.png")

    md = "![diagram](media/image1.emf)"
    result = img_mod.process_images(md, images_dir, media_dir=media_dir)
    assert "![diagram](images/image_0123456789abcdef.png)" in result
    assert "image1.emf" not in result


def test_media_conversion_failure_removes_reference(tmp_path) -> None:
    """A media image that cannot be converted is dropped from the md (its temp path is gone)."""
    images_dir = tmp_path / "images"
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    (media_dir / "bad.png").write_bytes(b"not-a-real-image")
    md = "before\n\n![x](media/bad.png)\n\nafter"
    result = process_images(md, images_dir, media_dir=media_dir)
    assert "![x]" not in result
    assert "media/bad.png" not in result
    assert "before" in result and "after" in result


def test_http_image_download_failure_keeps_url(tmp_path, monkeypatch) -> None:
    """A failed remote image download keeps the original URL (per design)."""
    import requests as _requests

    from aome_rag.cleaning import images as img_mod

    def _fail(url, **kw):
        raise _requests.ConnectionError("boom")

    monkeypatch.setattr(img_mod.requests, "get", _fail)

    images_dir = tmp_path / "images"
    md = "![img](https://example.com/pic.jpg)"
    result = img_mod.process_images(md, images_dir)
    assert "https://example.com/pic.jpg" in result  # original URL kept
