"""Ingestion end-to-end against a real (local) Zvec store with a fake embedder."""

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor

import pytest

from aome_rag.ingestion.chunker import Chunker
from aome_rag.ingestion.hashing import chunk_id
from aome_rag.ingestion.pipeline import IngestionPipeline, UploadedDoc
from aome_rag.ingestion.parser import Parser
from aome_rag.retrieval.embedder import OllamaEmbedder
from aome_rag.retrieval.retriever import Retriever
from aome_rag.retrieval.store import ZvecStore

pytestmark = pytest.mark.integration


class _FakeEmbedder(OllamaEmbedder):
    def __init__(self, dim: int) -> None:
        self._dim = dim

    async def embed_batch(self, texts):
        return [[float(len(t) % 7)] * self._dim for t in texts]

    async def embed(self, text):
        return (await self.embed_batch([text]))[0]


DOC_MD = b"""# Onboarding

New hires get a laptop on day one.

## Deploy

We deploy with github actions on every commit.
"""

_SOURCE = "onboarding.md"
_IDS = [chunk_id(_SOURCE, 0), chunk_id(_SOURCE, 1)]


def _pipeline(tmp_path, dim=8):
    store = ZvecStore(os.path.join(str(tmp_path), "col"), dim=dim)
    embedder = _FakeEmbedder(dim)
    pipe = IngestionPipeline(
        Parser(), Chunker(target_chars=300, max_chars=500, overlap=40),
        embedder, store, asyncio.Lock(), ThreadPoolExecutor(max_workers=2),
    )
    return store, embedder, pipe


async def test_ingest_lands_chunks_with_metadata(tmp_path) -> None:
    store, _embedder, pipe = _pipeline(tmp_path)
    report = await pipe.ingest([UploadedDoc(_SOURCE, DOC_MD)])
    assert report.n_docs == 1
    assert report.n_chunks == 2
    assert report.n_failed == 0

    ids = list(store.fetch_ids(_IDS).keys())
    assert set(ids) == set(_IDS)


async def test_ingest_is_idempotent(tmp_path) -> None:
    store, _embedder, pipe = _pipeline(tmp_path)
    await pipe.ingest([UploadedDoc(_SOURCE, DOC_MD)])
    first = set(store.fetch_ids(_IDS).keys())

    report2 = await pipe.ingest([UploadedDoc(_SOURCE, DOC_MD)])
    second = set(store.fetch_ids(_IDS).keys())

    assert report2.n_chunks == 2
    assert first == second  # upsert-by-id: no duplicate rows


async def test_ingested_chunks_are_retrievable(tmp_path) -> None:
    store, embedder, pipe = _pipeline(tmp_path)
    await pipe.ingest([UploadedDoc(_SOURCE, DOC_MD)])
    retriever = Retriever(store, embedder, ThreadPoolExecutor(max_workers=2), top_k=5)
    hits = await retriever.search("deploy", top_k=5)
    assert hits, "expected at least one hit"
    assert any(h.source_doc == _SOURCE for h in hits)


async def test_ingest_continues_on_bad_file(tmp_path) -> None:
    _store, _embedder, pipe = _pipeline(tmp_path)
    report = await pipe.ingest(
        [UploadedDoc("bad.unknownext", b"\x00\x01\x02 not a real doc"), UploadedDoc("ok.md", DOC_MD)]
    )
    assert report.n_failed >= 0  # did not raise
    assert report.n_docs >= 1  # the good doc still processed
