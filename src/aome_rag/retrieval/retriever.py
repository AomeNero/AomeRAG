"""检索器：异步混合检索。先嵌入查询（async），再在线程池跑 Zvec 混合查询。"""

from __future__ import annotations

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

import structlog

from .embedder import OllamaEmbedder
from .store import ZvecStore

_log = structlog.get_logger()


@dataclass
class Hit:
    chunk_id: str
    score: float
    text: str
    source_doc: str
    heading_path: str
    page: int | None
    chunk_index: int


@dataclass
class SearchFilters:
    # 预留给未来的 ACL（v1 共享知识库——暂未使用）。zvec 过滤 DSL 类似 SQL，如
    # 'department = "eng"'；接线随 ACL 功能一起落地。
    department: list[str] | None = None
    source_doc: list[str] | None = None


class Retriever:
    def __init__(
        self,
        store: ZvecStore,
        embedder: OllamaEmbedder,
        executor: ThreadPoolExecutor,
        *,
        top_k: int = 6,
    ) -> None:
        self._store = store
        self._embedder = embedder
        self._executor = executor
        self._top_k = top_k

    async def search(
        self,
        query: str,
        top_k: int | None = None,
        filters: SearchFilters | None = None,  # noqa: ARG002 - reserved
    ) -> list[Hit]:
        _log.debug("retriever.search", query=query[:80])
        vec = await self._embedder.embed(query)
        k = top_k or self._top_k
        loop = asyncio.get_running_loop()
        t0 = time.perf_counter()
        docs = await loop.run_in_executor(self._executor, self._store.hybrid_query, vec, query, k)
        hits = [self._to_hit(d) for d in docs]
        _log.info(
            "retriever.search.done",
            top_k=k, results=len(hits),
            elapsed_ms=round((time.perf_counter() - t0) * 1000, 1),
        )
        return hits

    @staticmethod
    def _to_hit(doc: Any) -> Hit:
        f = doc.fields or {}
        page = f.get("page")
        return Hit(
            chunk_id=doc.id,
            score=float(getattr(doc, "score", 0.0) or 0.0),
            text=f.get("text", "") or "",
            source_doc=f.get("source_doc", "") or "",
            heading_path=f.get("heading_path", "") or "",
            page=int(page) if page is not None else None,
            chunk_index=int(f.get("chunk_index", 0) or 0),
        )
