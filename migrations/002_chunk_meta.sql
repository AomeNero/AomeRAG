-- SQLite schema for the KB admin chunk-metadata side table (Phase: 知识库管理).
-- Mirrored in src/aome_rag/session/db.py `_SCHEMA` (auto-applied at open_db via
-- CREATE TABLE IF NOT EXISTS — existing DBs pick this up on next start).

CREATE TABLE IF NOT EXISTS chunk_meta (
    id           TEXT PRIMARY KEY,      -- zvec doc id: sha1(source_doc)[:16]#index
    source_doc   TEXT NOT NULL,         -- posix relative path in md-data/
    chunk_index  INTEGER NOT NULL,
    heading_path TEXT NOT NULL DEFAULT '',
    text_preview TEXT NOT NULL DEFAULT '',
    created_at   REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chunk_meta_source
    ON chunk_meta (source_doc, chunk_index);
