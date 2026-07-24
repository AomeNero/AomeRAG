"""Zvec collection schema for KB chunks.

Hybrid index: a dense HNSW (cosine) vector field for bge-m3 + an FTS-indexed text field for
the keyword channel. (Ollama exposes bge-m3 dense only; sparse is NOT used — see plan §7.)
Structured fields carry metadata; `department` is reserved for future ACL (unused in v1).
"""

from __future__ import annotations

import zvec

DENSE_FIELD = "dense"
TEXT_FIELD = "text"

# Metadata field names (stored per chunk).
F_SOURCE_DOC = "source_doc"
F_HEADING_PATH = "heading_path"
F_PAGE = "page"
F_CHUNK_INDEX = "chunk_index"
F_DEPARTMENT = "department"  # reserved for future ACL
F_CONTENT_HASH = "content_hash"
F_CREATED_AT = "created_at"

OUTPUT_FIELDS = [TEXT_FIELD, F_SOURCE_DOC, F_HEADING_PATH, F_PAGE, F_CHUNK_INDEX]


def build_collection_schema(dim: int, name: str = "kb_chunks_v1") -> "zvec.CollectionSchema":
    return zvec.CollectionSchema(
        name=name,
        fields=[
            zvec.FieldSchema(TEXT_FIELD, zvec.DataType.STRING, index_param=zvec.FtsIndexParam()),
            zvec.FieldSchema(F_SOURCE_DOC, zvec.DataType.STRING, index_param=zvec.InvertIndexParam()),
            zvec.FieldSchema(F_HEADING_PATH, zvec.DataType.STRING),
            zvec.FieldSchema(F_PAGE, zvec.DataType.INT32, nullable=True),
            zvec.FieldSchema(F_CHUNK_INDEX, zvec.DataType.INT32),
            zvec.FieldSchema(F_DEPARTMENT, zvec.DataType.STRING, index_param=zvec.InvertIndexParam()),
            zvec.FieldSchema(F_CONTENT_HASH, zvec.DataType.STRING, index_param=zvec.InvertIndexParam()),
            zvec.FieldSchema(F_CREATED_AT, zvec.DataType.INT64),
        ],
        vectors=[
            zvec.VectorSchema(
                DENSE_FIELD,
                zvec.DataType.VECTOR_FP32,
                dim,
                index_param=zvec.HnswIndexParam(metric_type=zvec.MetricType.COSINE),
            )
        ],
    )
