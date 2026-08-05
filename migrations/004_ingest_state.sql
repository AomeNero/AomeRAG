-- SQLite schema for the incremental-ingest state (which md-data files were sliced & their
-- content hash). Mirrored in src/aome_rag/session/db.py `_SCHEMA` (auto-applied).

CREATE TABLE IF NOT EXISTS ingest_state (
    path         TEXT PRIMARY KEY,   -- md relative path in md-data/ (= source_doc)
    content_hash TEXT NOT NULL,      -- sha1 of the md file bytes at last ingest
    updated_at   REAL NOT NULL
);
