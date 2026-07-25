"""Document converter: .docx → Pandoc, others → MarkItDown, .md → direct read."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from markitdown import MarkItDown

DIRECT_EXTS = {".md", ".markdown"}
PANDOC_EXTS = {".docx"}
MARKITDOWN_EXTS = {
    ".pdf", ".xlsx", ".pptx", ".html", ".htm", ".txt",
    ".csv", ".json", ".xml", ".yaml", ".yml",
}
SUPPORTED_EXTS = DIRECT_EXTS | PANDOC_EXTS | MARKITDOWN_EXTS


class UnsupportedDoc(Exception):
    pass


class Converter:
    """Routes by extension: .docx→pandoc (with --extract-media), others→markitdown, .md→direct."""

    def __init__(self) -> None:
        self._md = MarkItDown()

    def convert(self, src: Path) -> tuple[str, Path | None]:
        """Returns (markdown_text, media_dir | None). media_dir holds pandoc-extracted images."""
        ext = src.suffix.lower()
        if ext in DIRECT_EXTS:
            return src.read_text(encoding="utf-8", errors="replace"), None
        if ext in PANDOC_EXTS:
            return self._pandoc_docx(src)
        if ext in MARKITDOWN_EXTS:
            return self._md.convert(str(src)).text_content or "", None
        raise UnsupportedDoc(str(src))

    def _pandoc_docx(self, src: Path) -> tuple[str, Path | None]:
        """Convert .docx via pandoc with media extraction. Falls back to markitdown on error."""
        media_dir = Path(tempfile.mkdtemp(prefix="pandoc_media_"))
        out_md = media_dir / "_output.md"
        try:
            subprocess.run(
                [
                    "pandoc", str(src), "-t", "gfm",
                    "-o", str(out_md), "--extract-media", str(media_dir),
                ],
                check=True, capture_output=True, text=True, timeout=120,
            )
            text = out_md.read_text(encoding="utf-8") if out_md.exists() else ""
            out_md.unlink(missing_ok=True)
            return text, media_dir
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
            shutil.rmtree(media_dir, ignore_errors=True)
            return self._md.convert(str(src)).text_content or "", None
