"""Cleaning pipeline: full-regenerate raw-data → md-data (front-matter + images).

Async generator yielding SSE progress events (scan / file_start / file_done / skipped / summary).
Each run clears md-data (including images/) and rebuilds from raw-data."""

from __future__ import annotations

import asyncio
import hashlib
import shutil
import time
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import structlog

from .cleaner import SUPPORTED_EXTS, Converter
from .frontmatter import build_front_matter
from .images import process_images

_log = structlog.get_logger()


def _read_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


class CleaningPipeline:
    def __init__(
        self,
        converter: Converter,
        executor: ThreadPoolExecutor,
        clean_state: object | None = None,
    ) -> None:
        self._converter = converter
        self._executor = executor
        self._clean_state = clean_state  # optional CleanStateStore (for incremental_update)

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
                if p.name.startswith("~"):
                    continue  # Office temp / hidden files (~$xxx)
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

        # --- full regenerate: clear md-data, but NEVER delete the images/ pool ---
        if md.is_dir():
            for item in md.iterdir():
                if item.name == "images":
                    continue  # images accumulate across cleans; never remove them
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
                _log.info("clean.file", source_doc=rel, status="ok")
                yield {"type": "file_done", "source_doc": rel, "status": "ok"}
            except Exception as e:
                n_failed += 1
                errors.append(f"{rel}: {e}")
                _log.warning("clean.file", source_doc=rel, status="error", error=str(e))
                yield {
                    "type": "file_done",
                    "source_doc": rel,
                    "status": "error",
                    "error": str(e),
                }

        _log.info(
            "clean.done", n_docs=n_ok, n_failed=n_failed,
            elapsed_s=round(time.monotonic() - t0, 2),
        )
        yield {
            "type": "summary",
            "n_docs": n_ok,
            "n_failed": n_failed,
            "errors": errors,
            "elapsed_s": round(time.monotonic() - t0, 2),
        }

    async def incremental_update(
        self, raw_data_dir: str, md_data_dir: str
    ) -> AsyncIterator[dict]:
        """Incremental clean: only convert NEW/MODIFIED raw files (content-hash vs clean_state),
        delete the md output of REMOVED files, and persist the new state.

        Yields `deleted` events for removed docs and `file_done`/`file_start` for the
        converted ones — all using the RAW relative path; callers derive the md source_doc
        via `Path(rel).with_suffix(".md")`."""
        loop = asyncio.get_running_loop()
        raw = Path(raw_data_dir)
        md = Path(md_data_dir)
        images_dir = md / "images"
        t0 = time.monotonic()

        prev: dict[str, str] = {}
        if self._clean_state is not None:
            prev = await self._clean_state.load()
        scanned: set[str] = set()
        new_state: dict[str, str] = {}
        n_cleaned = 0
        n_skipped = 0
        n_failed = 0
        errors: list[str] = []

        # --- scan raw files ---
        files: list[tuple[str, Path]] = []
        skipped: list[str] = []
        if raw.is_dir():
            for p in sorted(raw.rglob("*")):
                if p.is_dir():
                    continue
                if p.name.startswith("~"):
                    continue  # Office temp / hidden files (~$xxx)
                rel = p.relative_to(raw).as_posix()
                scanned.add(rel)
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

        # --- removed files: drop from state + delete their md output ---
        for rel in prev:
            if rel not in scanned:
                md_file = md / Path(rel).with_suffix(".md")
                if md_file.is_file():
                    md_file.unlink(missing_ok=True)
                yield {"type": "deleted", "source_doc": rel}

        images_dir.mkdir(parents=True, exist_ok=True)

        # --- process only new/modified files ---
        for rel, path in files:
            try:
                data = await loop.run_in_executor(self._executor, _read_bytes, str(path))
                h = hashlib.sha1(data).hexdigest()
            except Exception as e:  # noqa: BLE001
                n_failed += 1
                errors.append(f"{rel}: {e}")
                yield {"type": "file_done", "source_doc": rel, "status": "error", "error": str(e)}
                continue

            if prev.get(rel) == h:
                new_state[rel] = h  # unchanged — keep state, skip conversion
                n_skipped += 1
                yield {"type": "file_skipped", "source_doc": rel}
                continue

            yield {"type": "file_start", "source_doc": rel}
            try:
                text, media_dir = await loop.run_in_executor(
                    self._executor, self._converter.convert, path
                )
                out_path = md / Path(rel).with_suffix(".md")
                out_path.parent.mkdir(parents=True, exist_ok=True)
                text = await loop.run_in_executor(
                    self._executor, process_images, text, images_dir, media_dir, out_path.parent
                )
                fm = build_front_matter(path.stem)
                out_path.write_text(fm + text, encoding="utf-8")
                if media_dir and media_dir.is_dir():
                    shutil.rmtree(media_dir, ignore_errors=True)
                new_state[rel] = h
                n_cleaned += 1
                yield {"type": "file_done", "source_doc": rel, "status": "ok"}
            except Exception as e:  # noqa: BLE001
                n_failed += 1
                errors.append(f"{rel}: {e}")
                yield {"type": "file_done", "source_doc": rel, "status": "error", "error": str(e)}

        # --- persist new state (only successfully handled + still-present files) ---
        if self._clean_state is not None:
            await self._clean_state.save_all(new_state)

        _log.info(
            "clean.incremental.done", n_cleaned=n_cleaned, n_skipped=n_skipped,
            n_failed=n_failed, n_deleted=len(set(prev) - scanned),
            elapsed_s=round(time.monotonic() - t0, 2),
        )
        yield {
            "type": "summary",
            "n_cleaned": n_cleaned,
            "n_skipped": n_skipped,
            "n_failed": n_failed,
            "n_deleted": len(set(prev) - scanned),
            "errors": errors,
            "elapsed_s": round(time.monotonic() - t0, 2),
        }
