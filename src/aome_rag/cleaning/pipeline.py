"""清洗管线：全量重生成 raw-data → md-data（front-matter + 图片），SSE 进度。"""

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

        # --- 扫描 ---
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

        # --- 全量重生成：清空 md-data，但绝不删除 images/ 池 ---
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

        # --- 逐个处理文件 ---
        n_ok = 0
        n_failed = 0
        errors: list[str] = []

        for rel, path in files:
            yield {"type": "file_start", "source_doc": rel}
            try:
                text, media_dir = await loop.run_in_executor(
                    self._executor, self._converter.convert, path
                )
                # 镜像 raw-data 的子目录结构：raw/sub/file.docx → md/sub/file.md
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
        """增量清洗：只转换新增/变更的 raw 文件（内容哈希对比 clean_state），
        删除已移除文件的 md 输出，并持久化新状态。

        为移除的文档产出 `deleted` 事件，为转换的产出 `file_done`/`file_start`——
        都用 raw 相对路径；调用方用 `Path(rel).with_suffix(".md")` 推导 md source_doc。"""
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

        # --- 扫描 raw 文件 ---
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

        # --- 已删除文件：从状态移除并删除其 md 输出 ---
        for rel in prev:
            if rel not in scanned:
                md_file = md / Path(rel).with_suffix(".md")
                if md_file.is_file():
                    md_file.unlink(missing_ok=True)
                yield {"type": "deleted", "source_doc": rel}

        images_dir.mkdir(parents=True, exist_ok=True)

        # --- 只处理新增/变更文件 ---
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

        # --- 持久化新状态（仅成功处理且仍存在的文件）---
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
