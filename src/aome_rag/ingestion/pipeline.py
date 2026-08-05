"""Ingestion pipeline. Two entry points sharing chunk -> embed -> [lock: delete + upsert]:

- ingest(docs)            for uploaded bytes (multipart /ingest) -> IngestReport
- ingest_files(files)     for a directory scan (/ingest/dir, SSE) -> async generator of
                          per-file progress dicts, ending with a summary

Both do per-file delete-then-insert (delete_by_source before upsert), so editing a file
shorter / re-chunking leaves no stale chunks."""

from __future__ import annotations

import asyncio
import hashlib
import os
import time
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from ..retrieval.embedder import OllamaEmbedder
from ..retrieval.store import ZvecStore
from .chunker import Chunker
from .hashing import chunk_id, content_hash
from .parser import Parser, UnsupportedFile


@dataclass
class UploadedDoc:
    filename: str
    data: bytes


@dataclass
class IngestReport:
    n_docs: int = 0
    n_chunks: int = 0
    n_failed: int = 0
    errors: list[str] = field(default_factory=list)
    elapsed_s: float = 0.0


def _read_file(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


class IngestionPipeline:
    def __init__(
        self,
        parser: Parser,
        chunker: Chunker,
        embedder: OllamaEmbedder,
        store: ZvecStore,
        write_lock: asyncio.Lock,
        executor: ThreadPoolExecutor,
        *,
        embed_batch: int = 16,
        chunk_meta: object | None = None,
        ingest_state: object | None = None,
    ) -> None:
        self._parser = parser
        self._chunker = chunker
        self._embedder = embedder
        self._store = store
        self._lock = write_lock
        self._executor = executor
        self._batch = embed_batch
        self._chunk_meta = chunk_meta  # optional ChunkMetaStore — None in legacy call sites
        self._ingest_state = ingest_state  # optional StateStore — None in legacy call sites

    async def _make_chunks(
        self, source_doc: str, markdown: str, department: str | None
    ) -> list[dict]:
        pieces = self._chunker.split(markdown, source_doc=source_doc)
        if not pieces:
            return []
        texts = [p["text"] for p in pieces]
        vectors: list[list[float]] = []
        for i in range(0, len(texts), self._batch):
            vectors.extend(await self._embedder.embed_batch(texts[i : i + self._batch]))
        now = int(time.time())
        return [
            {
                "id": chunk_id(source_doc, p["chunk_index"]),
                "dense": vec,
                "text": p["text"],
                "source_doc": source_doc,
                "heading_path": p["heading_path"],
                "page": p.get("page"),
                "chunk_index": p["chunk_index"],
                "department": department or "",
                "content_hash": content_hash(p["text"]),
                "created_at": now,
            }
            for p, vec in zip(pieces, vectors, strict=True)
        ]

    async def _delete_and_upsert(self, source_doc: str, chunks: list[dict]) -> None:
        loop = asyncio.get_running_loop()
        async with self._lock:
            await loop.run_in_executor(self._executor, self._store.delete_by_source, source_doc)
            if chunks:
                await loop.run_in_executor(self._executor, self._store.upsert_chunks, chunks)
            if self._chunk_meta is not None:
                await self._chunk_meta.replace_source(
                    source_doc,
                    [
                        {
                            "id": c["id"],
                            "chunk_index": c["chunk_index"],
                            "heading_path": c.get("heading_path", ""),
                            "text_preview": (c.get("text") or "")[:200],
                            "created_at": c.get("created_at", 0),
                        }
                        for c in chunks
                    ],
                )

    async def ingest(
        self, docs: list[UploadedDoc], department: str | None = None
    ) -> IngestReport:
        loop = asyncio.get_running_loop()
        t0 = time.monotonic()
        report = IngestReport()
        for doc in docs:
            try:
                markdown = await loop.run_in_executor(
                    self._executor, self._parser.parse, doc.filename, doc.data
                )
                chunks = await self._make_chunks(doc.filename, markdown, department)
                await self._delete_and_upsert(doc.filename, chunks)
                report.n_docs += 1
                report.n_chunks += len(chunks)
            except UnsupportedFile:
                report.n_failed += 1
                report.errors.append(f"{doc.filename}: unsupported file type")
            except Exception as e:  # noqa: BLE001
                report.n_failed += 1
                report.errors.append(f"{doc.filename}: {e}")
        report.elapsed_s = time.monotonic() - t0
        return report

    async def ingest_files(
        self, files: list[tuple[str, str]], department: str | None = None
    ) -> AsyncIterator[dict]:
        """`files`: list of (source_doc, absolute_path). Yields per-file progress dicts,
        then a final summary dict. Per file: read -> parse -> chunk -> embed -> delete+upsert."""
        loop = asyncio.get_running_loop()
        t0 = time.monotonic()
        report = IngestReport()
        for source_doc, path in files:
            yield {"type": "file_start", "source_doc": source_doc}
            try:
                data = await loop.run_in_executor(self._executor, _read_file, path)
                markdown = await loop.run_in_executor(
                    self._executor, self._parser.parse, os.path.basename(path), data
                )
                chunks = await self._make_chunks(source_doc, markdown, department)
                await self._delete_and_upsert(source_doc, chunks)
                report.n_docs += 1
                report.n_chunks += len(chunks)
                yield {
                    "type": "file_done",
                    "source_doc": source_doc,
                    "n_chunks": len(chunks),
                    "status": "ok",
                }
            except UnsupportedFile:
                yield {
                    "type": "skipped",
                    "source_doc": source_doc,
                    "reason": "unsupported extension",
                }
            except Exception as e:  # noqa: BLE001 - one bad file must not abort the batch
                report.n_failed += 1
                report.errors.append(f"{source_doc}: {e}")
                yield {
                    "type": "file_done",
                    "source_doc": source_doc,
                    "n_chunks": 0,
                    "status": "error",
                    "error": str(e),
                }
        report.elapsed_s = time.monotonic() - t0
        yield {
            "type": "summary",
            "n_docs": report.n_docs,
            "n_chunks": report.n_chunks,
            "n_failed": report.n_failed,
            "errors": report.errors,
            "elapsed_s": report.elapsed_s,
        }

    async def reingest_one(self, source_doc: str, md_data_dir: str) -> IngestReport:
        """Re-ingest a single md-data document (chunk + embed + delete-then-insert).
        Needs Ollama online (embedding). Returns an IngestReport."""
        report = IngestReport()
        path = Path(md_data_dir) / source_doc
        async for ev in self.ingest_files([(source_doc, str(path))]):
            if ev["type"] == "summary":
                report.n_docs = ev["n_docs"]
                report.n_chunks = ev["n_chunks"]
                report.n_failed = ev["n_failed"]
                report.errors = ev["errors"]
        return report

    async def sync_meta(self, md_data_dir: str) -> dict:
        """Rebuild the chunk-meta side table from md-data files WITHOUT re-embedding.

        For each .md file: re-chunk with the current chunker, then verify which candidate
        chunk ids actually exist in the zvec collection (via fetch) — so the side table only
        records chunks that are really indexed (docs never ingested stay 'unsliced')."""
        loop = asyncio.get_running_loop()
        base = Path(md_data_dir)
        counts = {"n_docs": 0, "n_chunks": 0, "n_skipped": 0}
        if self._chunk_meta is None:
            return counts
        if not base.is_dir():
            return counts
        for p in sorted(base.rglob("*")):
            rel = p.relative_to(base).as_posix()
            if rel.startswith("images/") or rel == "images":
                continue
            if not p.is_file() or p.suffix.lower() != ".md":
                continue
            try:
                markdown = p.read_text(encoding="utf-8", errors="replace")
                pieces = self._chunker.split(markdown, source_doc=rel)
                if not pieces:
                    continue
                ids = [chunk_id(rel, pc["chunk_index"]) for pc in pieces]
                existing = await loop.run_in_executor(self._executor, self._store.fetch_ids, ids)
                meta = [
                    {
                        "id": cid,
                        "chunk_index": pc["chunk_index"],
                        "heading_path": pc.get("heading_path", ""),
                        "text_preview": (pc.get("text") or "")[:200],
                        "created_at": int(time.time()),
                    }
                    for cid, pc in zip(ids, pieces, strict=True)
                    if cid in existing
                ]
                if meta:
                    await self._chunk_meta.replace_source(rel, meta)
                    counts["n_docs"] += 1
                    counts["n_chunks"] += len(meta)
                else:
                    await self._chunk_meta.delete_source(rel)
                    counts["n_skipped"] += 1
            except Exception:  # noqa: BLE001 - one bad file must not abort the sync
                continue
        return counts

    async def incremental_ingest(self, md_data_dir: str) -> AsyncIterator[dict]:
        """Incremental ingest: only re-ingest NEW/MODIFIED md files (content-hash vs
        ingest_state), remove chunks for REMOVED docs, and persist the new state.
        Needs Ollama online (embedding). Yields scan / file_start / file_done / skipped /
        deleted / summary events."""
        loop = asyncio.get_running_loop()
        base = Path(md_data_dir)
        t0 = time.monotonic()
        prev: dict[str, str] = {}
        if self._ingest_state is not None:
            prev = await self._ingest_state.load()
        scanned: set[str] = set()
        new_state: dict[str, str] = {}
        pending: list[tuple[str, str]] = []  # (source_doc, abs path) for changed/new
        n_skipped = 0

        if base.is_dir():
            for p in sorted(base.rglob("*")):
                rel = p.relative_to(base).as_posix()
                if rel.startswith("images/") or rel == "images":
                    continue
                if p.name.startswith("~"):
                    continue  # temp/hidden files
                if not p.is_file() or p.suffix.lower() != ".md":
                    continue
                scanned.add(rel)
                try:
                    data = await loop.run_in_executor(self._executor, _read_file, str(p))
                    h = hashlib.sha1(data).hexdigest()
                except Exception:  # noqa: BLE001
                    continue  # unreadable → not recorded, retried next time
                new_state[rel] = h
                if prev.get(rel) == h:
                    n_skipped += 1
                    yield {"type": "file_skipped", "source_doc": rel}
                else:
                    pending.append((rel, str(p)))

        yield {"type": "scan", "raw_dir": md_data_dir, "n_files": len(scanned)}

        n_ingested = 0
        if pending:
            async for ev in self.ingest_files(pending):
                if ev["type"] == "summary":
                    continue  # we emit our own summary at the end
                if ev["type"] == "file_done" and ev.get("status") == "ok":
                    n_ingested += 1
                elif ev["type"] == "file_done" and ev.get("status") == "error":
                    new_state.pop(ev["source_doc"], None)  # failed → retry next time
                yield ev

        # remove chunks for removed docs
        n_deleted = 0
        for doc in prev:
            if doc not in scanned:
                async with self._lock:
                    await loop.run_in_executor(self._executor, self._store.delete_by_source, doc)
                    if self._chunk_meta is not None:
                        await self._chunk_meta.delete_source(doc)
                n_deleted += 1
                yield {"type": "deleted", "source_doc": doc}

        if self._ingest_state is not None:
            await self._ingest_state.save_all(new_state)

        yield {
            "type": "summary",
            "n_ingested": n_ingested,
            "n_skipped": n_skipped,
            "n_deleted": n_deleted,
            "errors": [],
            "elapsed_s": round(time.monotonic() - t0, 2),
        }
