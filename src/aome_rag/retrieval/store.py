"""Zvec store. All zvec calls are synchronous (C bindings) — callers MUST run them via a
threadpool executor (see Retriever / IngestionPipeline). Writes need an external lock because
zvec writes are single-process exclusive."""

from __future__ import annotations

import os
from typing import Any

import zvec

from .schema import DENSE_FIELD, F_SOURCE_DOC, OUTPUT_FIELDS, TEXT_FIELD, build_collection_schema


class ZvecStore:
    def __init__(self, path: str, dim: int, collection_name: str = "kb_chunks_v1") -> None:
        self.path = path
        self._dim = dim
        self._collection_name = collection_name
        if os.path.exists(path):
            self._col = zvec.open(path)
        else:
            parent = os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            self._col = zvec.create_and_open(path, build_collection_schema(dim, collection_name))

    def upsert_chunks(self, chunks: list[dict[str, Any]]) -> None:
        """Insert/replace chunks by id. Each chunk dict carries `id`, `dense`, and metadata
        fields matching retrieval.schema."""
        docs = [
            zvec.Doc(
                id=c["id"],
                vectors={DENSE_FIELD: c["dense"]},
                fields={
                    TEXT_FIELD: c.get("text", ""),
                    "source_doc": c.get("source_doc", ""),
                    "heading_path": c.get("heading_path", ""),
                    "page": c.get("page"),
                    "chunk_index": c.get("chunk_index", 0),
                    "department": c.get("department", ""),
                    "content_hash": c.get("content_hash", ""),
                    "created_at": c.get("created_at", 0),
                },
            )
            for c in chunks
        ]
        self._col.upsert(docs)
        self._col.flush()

    def hybrid_query(
        self, dense_vec: list[float], fts_query: str, top_k: int
    ) -> list["zvec.Doc"]:
        """Fuse dense (HNSW cosine) + FTS via RRF. Returns docs pre-ranked best-first."""
        queries = [
            zvec.Query(field_name=DENSE_FIELD, vector=list(dense_vec)),
            zvec.Query(field_name=TEXT_FIELD, fts=zvec.Fts(query_string=fts_query)),
        ]
        return self._col.query(
            queries, topk=top_k, reranker=zvec.RrfReRanker(), output_fields=OUTPUT_FIELDS
        )

    def fetch_ids(self, ids: list[str]) -> dict[str, "zvec.Doc"]:
        return self._col.fetch(ids, include_vector=False)

    def delete_by_source(self, source_doc: str) -> None:
        """Delete all chunks of one source document (delete-then-insert on re-ingest).
        zvec filter DSL is SQL-like with a single `=`; string literal in double quotes."""
        self._col.delete_by_filter(f'{F_SOURCE_DOC} = "{source_doc}"')
        self._col.flush()

    def chunk_count(self) -> int:
        """Total number of chunks in the collection."""
        return self._col.stats.doc_count

    def clear(self) -> None:
        """Destroy and recreate the collection (danger zone — wipes all chunks)."""
        self._col.destroy()
        self._col = zvec.create_and_open(
            self.path, build_collection_schema(self._dim, self._collection_name)
        )
