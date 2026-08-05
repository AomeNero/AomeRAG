"""Cleaning pipeline: full-regenerate raw-data → md-data (front-matter + images).

Async generator yielding SSE progress events (scan / file_start / file_done / skipped / summary).
Each run clears md-data (including images/) and rebuilds from raw-data."""

from __future__ import annotations

import asyncio
import shutil
import time
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .cleaner import SUPPORTED_EXTS, Converter
from .frontmatter import build_front_matter
from .images import process_images


class CleaningPipeline:
    def __init__(self, converter: Converter, executor: ThreadPoolExecutor) -> None:
        self._converter = converter
        self._executor = executor

    async def clean_dir(
        self, raw_data_dir: str, md_data_dir: str
    ) -> AsyncIterator[dict]:
        loop = asyncio.get_running_loop()
        raw = Path(raw_data_dir)
        md = Path(md_data_dir)
        images_dir = md / "images"
        t0 = time.monotonic()

        # --- scan ---
        files: list[tuple[str, Path]] = []
        skipped: list[str] = []
        if raw.is_dir():
            for p in sorted(raw.rglob("*")):
                if p.is_dir():
                    continue
                rel = p.relative_to(raw).as_posix()
                if p.suffix.lower() in SUPPORTED_EXTS:
                    files.append((rel, p))
                else:
                    skipped.append(rel)

        yield {
            "type": "scan",
            "raw_dir": raw_data_dir,
            "n_files": len(files),
            "n_skipped": len(skipped),
        }
        for s in skipped:
            yield {"type": "skipped", "source_doc": s, "reason": "unsupported extension"}

        # --- full regenerate: clear md-data ---
        if md.is_dir():
            for item in md.iterdir():
                if item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
                else:
                    item.unlink()
        md.mkdir(parents=True, exist_ok=True)
        images_dir.mkdir(parents=True, exist_ok=True)

        # --- process each file ---
        n_ok = 0
        n_failed = 0
        errors: list[str] = []

        for rel, path in files:
            yield {"type": "file_start", "source_doc": rel}
            try:
                text, media_dir = await loop.run_in_executor(
                    self._executor, self._converter.convert, path
                )
                # Mirror raw-data's subdirectory structure: raw/sub/file.docx → md/sub/file.md
                out_path = md / Path(rel).with_suffix(".md")
                out_path.parent.mkdir(parents=True, exist_ok=True)
                text = await loop.run_in_executor(
                    self._executor, process_images, text, images_dir, media_dir, out_path.parent
                )
                fm = build_front_matter(path.stem)
                out_path.write_text(fm + text, encoding="utf-8")
                if media_dir and media_dir.is_dir():
                    shutil.rmtree(media_dir, ignore_errors=True)
                n_ok += 1
                yield {"type": "file_done", "source_doc": rel, "status": "ok"}
            except Exception as e:
                n_failed += 1
                errors.append(f"{rel}: {e}")
                yield {
                    "type": "file_done",
                    "source_doc": rel,
                    "status": "error",
                    "error": str(e),
                }

        yield {
            "type": "summary",
            "n_docs": n_ok,
            "n_failed": n_failed,
            "errors": errors,
            "elapsed_s": round(time.monotonic() - t0, 2),
        }
