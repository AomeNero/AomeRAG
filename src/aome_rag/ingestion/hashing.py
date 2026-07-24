"""Stable content hashing + deterministic chunk ids for idempotent ingestion."""

from __future__ import annotations

import hashlib


def content_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def chunk_id(source_doc: str, chunk_index: int) -> str:
    """Deterministic, Zvec-safe chunk id.

    Zvec doc ids reject spaces / CJK / path separators, so we cannot use the source_doc
    string directly. Use a short hash of source_doc + the index — stable across re-ingest
    (so upsert replaces), and only [0-9a-f#] characters (all Zvec-safe). source_doc itself
    is stored as a field and used for filtering / display."""
    h = hashlib.sha1(source_doc.encode("utf-8")).hexdigest()[:16]
    return f"{h}#{chunk_index}"

