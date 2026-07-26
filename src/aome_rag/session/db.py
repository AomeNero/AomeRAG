"""SQLite connection factory. WAL mode + busy_timeout for single-writer concurrency;
schema mirrors migrations/001_init_sessions.sql."""

from __future__ import annotations

from pathlib import Path

import aiosqlite

_PRAGMAS = (
    "PRAGMA journal_mode=WAL",
    "PRAGMA synchronous=NORMAL",
    "PRAGMA busy_timeout=5000",
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL,
    title      TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions (user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS messages (
    id           TEXT PRIMARY KEY,
    session_id   TEXT NOT NULL,
    user_id      TEXT NOT NULL,
    role         TEXT NOT NULL,
    content_json TEXT NOT NULL,
    created_at   REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages (session_id, created_at);

CREATE TABLE IF NOT EXISTS feedback (
    id            TEXT PRIMARY KEY,
    type          TEXT NOT NULL,
    session_id    TEXT,
    user_id       TEXT NOT NULL,
    message_id    TEXT,
    rating        TEXT,
    user_question TEXT,
    ai_answer     TEXT,
    comment       TEXT,
    created_at    REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_feedback_created ON feedback (created_at DESC);
"""


async def open_db(path: str) -> aiosqlite.Connection:
    parent = Path(path).parent
    parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(path)
    db.row_factory = aiosqlite.Row
    for pragma in _PRAGMAS:
        await db.execute(pragma)
    await db.executescript(_SCHEMA)
    await db.commit()
    return db
