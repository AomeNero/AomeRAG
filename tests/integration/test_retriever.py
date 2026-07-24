"""Hybrid retrieval over a real (local) Zvec collection. Uses a fake embedder that maps
keywords -> orthogonal topic vectors, so dense + FTS channels both rank the target topic first.
No Ollama / no network required."""

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor

import pytest

from aome_rag.retrieval.embedder import OllamaEmbedder
from aome_rag.retrieval.retriever import Retriever
from aome_rag.retrieval.store import ZvecStore

pytestmark = pytest.mark.integration

DIM = 8


def _topic_vec(slot: int) -> list[float]:
    v = [0.0] * DIM
    v[slot] = 1.0
    return v


class FakeEmbedder(OllamaEmbedder):
    """Bypasses __init__ (no HTTP); maps a keyword in the text to a topic vector."""

    def __init__(self) -> None:  # noqa: D401
        self._map = {"deploy": _topic_vec(0), "onboard": _topic_vec(1), "billing": _topic_vec(2)}

    async def embed(self, text: str) -> list[float]:
        low = text.lower()
        for kw, v in self._map.items():
            if kw in low:
                return v
        return [0.0] * DIM


CHUNKS = [
    {"id": "devops.md#0", "dense": _topic_vec(0), "text": "how to deploy the service with github actions",
     "source_doc": "devops.md", "heading_path": "Deploy", "page": 1, "chunk_index": 0},
    {"id": "devops.md#1", "dense": _topic_vec(0), "text": "the deploy pipeline runs on every commit",
     "source_doc": "devops.md", "heading_path": "Deploy", "page": 2, "chunk_index": 1},
    {"id": "hr.md#0", "dense": _topic_vec(1), "text": "onboarding a new hire takes three days",
     "source_doc": "hr.md", "heading_path": "Onboarding", "page": 1, "chunk_index": 0},
    {"id": "hr.md#1", "dense": _topic_vec(1), "text": "laptop setup during onboarding",
     "source_doc": "hr.md", "heading_path": "Onboarding", "page": 3, "chunk_index": 1},
    {"id": "fin.md#0", "dense": _topic_vec(2), "text": "billing invoices are sent monthly",
     "source_doc": "fin.md", "heading_path": "Billing", "page": 1, "chunk_index": 0},
]


def _make_store(tmp_path) -> ZvecStore:
    path = os.path.join(str(tmp_path), "col")  # collection path must not pre-exist
    return ZvecStore(path, dim=DIM)


def test_upsert_then_dense_recall(tmp_path) -> None:
    store = _make_store(tmp_path)
    store.upsert_chunks(CHUNKS)
    # dense-only: query vector == topic 0 -> both devops chunks at top
    docs = store.hybrid_query(_topic_vec(0), "deploy", top_k=5)
    ids = {d.id for d in docs[:2]}
    assert ids == {"devops.md#0", "devops.md#1"}


async def test_retriever_search_returns_deploy_hits(tmp_path) -> None:
    store = _make_store(tmp_path)
    store.upsert_chunks(CHUNKS)
    retriever = Retriever(store, FakeEmbedder(), ThreadPoolExecutor(max_workers=2), top_k=4)

    hits = await retriever.search("how do I deploy?", top_k=4)

    sources = [h.source_doc for h in hits]
    # both deploy chunks should be retrieved (recall)
    assert sources.count("devops.md") == 2
    # top hit is a deploy chunk, with metadata populated
    top = hits[0]
    assert top.source_doc == "devops.md"
    assert top.text and top.chunk_id.startswith("devops.md")
    assert "deploy" in top.text.lower()


async def test_retriever_search_onboard_topic(tmp_path) -> None:
    store = _make_store(tmp_path)
    store.upsert_chunks(CHUNKS)
    retriever = Retriever(store, FakeEmbedder(), ThreadPoolExecutor(max_workers=2), top_k=2)

    hits = await retriever.search("onboarding process", top_k=2)
    assert all(h.source_doc == "hr.md" for h in hits)
