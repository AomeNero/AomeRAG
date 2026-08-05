-- SQLite schema for the incremental-clean state (which raw files were cleaned & their
-- content hash). Mirrored in src/aome_rag/session/db.py `_SCHEMA` (auto-applied).

CREATE TABLE IF NOT EXISTS clean_state (
    path         TEXT PRIMARY KEY,   -- raw relative path in raw-data/
    content_hash TEXT NOT NULL,      -- sha1 of the raw file bytes at last clean
    updated_at   REAL NOT NULL
);
