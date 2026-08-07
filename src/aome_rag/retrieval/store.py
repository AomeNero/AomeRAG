"""Zvec 存储。所有 zvec 调用同步（C 绑定），由调用方放线程池。"""

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
        """按 id 插入/替换 chunk。每个 chunk dict 含 `id`、`dense` 及与
        retrieval.schema 匹配的元数据字段。"""
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
        """用 RRF 融合 dense（HNSW 余弦）+ FTS。返回按最优优先排好的文档。"""
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
        """删除某个源文档的所有 chunk（重新入库时先删后插）。
        zvec 过滤 DSL 类似 SQL，只支持单个 `=`；字符串字面量用双引号。"""
        self._col.delete_by_filter(f'{F_SOURCE_DOC} = "{source_doc}"')
        self._col.flush()

    def delete_chunk(self, chunk_id: str) -> None:
        """按（zvec 安全的）id 删除单个 chunk。"""
        self._col.delete(chunk_id)
        self._col.flush()

    def chunk_count(self) -> int:
        """集合中的 chunk 总数。"""
        return self._col.stats.doc_count

    def clear(self) -> None:
        """销毁并重建集合（危险操作——清空所有 chunk）。"""
        self._col.destroy()
        self._col = zvec.create_and_open(
            self.path, build_collection_schema(self._dim, self._collection_name)
        )
