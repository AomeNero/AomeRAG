"""Document parsing — routes by extension.

Markdown files are read directly (they are already the target format, so markitdown would be
a no-op pass-through). Office/web text formats go through markitdown. Anything else is
unsupported and skipped by the caller."""

from __future__ import annotations

import io
import os

DIRECT_EXTS = {".md", ".markdown"}
MARKITDOWN_EXTS = {
    ".pdf", ".docx", ".pptx", ".xlsx",
    ".html", ".htm", ".txt", ".csv", ".json", ".xml", ".yaml", ".yml",
}
SUPPORTED_EXTS = DIRECT_EXTS | MARKITDOWN_EXTS


class UnsupportedFile(Exception):
    pass


class Parser:
    def __init__(self) -> None:
        from markitdown import MarkItDown

        self._md = MarkItDown()

    def parse(self, filename: str, data: bytes) -> str:
        """Return Markdown text for the file, routing by extension."""
        ext = os.path.splitext(filename)[1].lower()
        if ext in DIRECT_EXTS:
            return data.decode("utf-8", errors="replace")
        if ext in MARKITDOWN_EXTS:
            result = self._md.convert_stream(io.BytesIO(data), file_extension=ext or ".txt")
            return result.text_content or ""
        raise UnsupportedFile(filename)

    def parse_path(self, path: str) -> str:
        with open(path, "rb") as f:
            return self.parse(os.path.basename(path), f.read())
