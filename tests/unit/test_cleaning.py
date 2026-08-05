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


def test_image_name_strict_timestamp_format(tmp_path) -> None:
    """Extracted images must be named image_<YYYYmmddHHMMSSffffff>.png (strict)."""
    images_dir = tmp_path / "images"
    buf = io.BytesIO()
    Image.new("RGB", (2, 2), (255, 0, 0)).save(buf, "PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    process_images(f"![dot](data:image/png;base64,{b64})", images_dir)
    pngs = list(images_dir.glob("image_*.png"))
    assert len(pngs) == 1
    assert re.fullmatch(r"image_\d{20}\.png", pngs[0].name)


def test_image_name_collision_keeps_strict_format(tmp_path, monkeypatch) -> None:
    """Two images saved at the same wall-clock time must NOT get a _N suffix — each
    retries with a fresh timestamp, so names stay strictly image_<20 digits>.png."""
    import datetime as _dt

    from aome_rag.cleaning import images as img_mod

    times = iter(
        [
            _dt.datetime(2023, 10, 25, 14, 30, 25, 123456),
            _dt.datetime(2023, 10, 25, 14, 30, 25, 123456),  # same ms → collision
            _dt.datetime(2023, 10, 25, 14, 30, 25, 123457),  # fresh timestamp
        ]
    )

    class _FakeDt:
        @staticmethod
        def now():
            return next(times)

    monkeypatch.setattr(img_mod, "datetime", _FakeDt)

    images_dir = tmp_path / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    Image.new("RGB", (2, 2), (255, 0, 0)).save(buf, "PNG")
    data = buf.getvalue()
    img_mod._save_png(data, images_dir)
    img_mod._save_png(data, images_dir)

    names = sorted(p.name for p in images_dir.glob("image_*.png"))
    assert len(names) == 2
    assert all(re.fullmatch(r"image_\d{20}\.png", n) for n in names)


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
