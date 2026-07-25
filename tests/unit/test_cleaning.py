"""Unit tests for cleaning: front-matter + image extraction."""

import base64
import io
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
