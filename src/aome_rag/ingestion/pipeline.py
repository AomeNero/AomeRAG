"""Ingestion pipeline. Two entry points sharing chunk -> embed -> [lock: delete + upsert]:

- ingest(docs)            for uploaded bytes (multipart /ingest) -> IngestReport
- ingest_files(files)     for a directory scan (/ingest/dir, SSE) -> async generator of
                          per-file progress dicts, ending with a summary

Both do per-file delete-then-insert (delete_by_source before upsert), so editing a file
shorter / re-chunking leaves no stale chunks."""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

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
    ) -> None:
        self._parser = parser
        self._chunker = chunker
        self._embedder = embedder
        self._store = store
        self._lock = write_lock
        self._executor = executor
        self._batch = embed_batch

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
