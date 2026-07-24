"""ingest_files (the /ingest/dir engine): per-file delete-then-insert leaves no stale chunks
when a file is re-cut shorter."""

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor

import pytest

from aome_rag.ingestion.chunker import Chunker
from aome_rag.ingestion.hashing import chunk_id
from aome_rag.ingestion.parser import Parser
from aome_rag.ingestion.pipeline import IngestionPipeline
from aome_rag.retrieval.embedder import OllamaEmbedder
from aome_rag.retrieval.store import ZvecStore

pytestmark = pytest.mark.integration


class _FakeEmbedder(OllamaEmbedder):
    def __init__(self, dim: int) -> None:
        self._d = dim

    async def embed_batch(self, texts):
        return [[0.1] * self._d for _ in texts]


def _pipeline(tmp_path, dim=4):
    store = ZvecStore(os.path.join(str(tmp_path), "col"), dim=dim)
    pipe = IngestionPipeline(
        Parser(),
        Chunker(target_chars=50, max_chars=80, overlap=10),
        _FakeEmbedder(dim),
        store,
        asyncio.Lock(),
        ThreadPoolExecutor(max_workers=2),
    )
    return store, pipe


def _write(tmp_path, name, body):
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return str(path)


async def test_delete_then_insert_no_stale_after_shorten(tmp_path) -> None:
    store, pipe = _pipeline(tmp_path)
    long_md = "# H\n\n" + "\n\n".join(f"paragraph number {i}" for i in range(20))
    events = [e async for e in pipe.ingest_files([("doc.md", _write(tmp_path, "doc.md", long_md))])]
    n_first = next(e for e in events if e["type"] == "file_done")["n_chunks"]
    assert n_first > 1
    ids_first = [chunk_id("doc.md", i) for i in range(n_first)]
    assert set(store.fetch_ids(ids_first).keys()) == set(ids_first)

    # rewrite SHORTER and re-ingest
    _write(tmp_path, "doc.md", "# H\n\nonly one short paragraph here")
    events2 = [e async for e in pipe.ingest_files([("doc.md", str(tmp_path / "doc.md"))])]
    done = next(e for e in events2 if e["type"] == "file_done")
    assert done["n_chunks"] == 1
    assert events2[-1]["type"] == "summary"

    got = store.fetch_ids(ids_first)
    assert chunk_id("doc.md", 0) in got  # the one new chunk
    assert all(chunk_id("doc.md", i) not in got for i in range(1, n_first))  # stale gone


async def test_ingest_files_recursive_subdir_source_id(tmp_path) -> None:
    store, pipe = _pipeline(tmp_path)
    path = _write(tmp_path / "sub", "deep.md", "# Deep\n\nsome content")
    events = [e async for e in pipe.ingest_files([("sub/deep.md", path)])]
    assert events[0] == {"type": "file_start", "source_doc": "sub/deep.md"}
    assert store.fetch_ids([chunk_id("sub/deep.md", 0)])
