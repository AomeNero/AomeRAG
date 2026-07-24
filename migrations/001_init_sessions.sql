-- SQLite schema for multi-user conversation history (Phase 6).
-- Run with PRAGMA journal_mode=WAL; synchronous=NORMAL; busy_timeout=5000.

CREATE TABLE IF NOT EXISTS sessions (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL,
    title      TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sessions_user
    ON sessions (user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS messages (
    id           TEXT PRIMARY KEY,
    session_id   TEXT NOT NULL,
    user_id      TEXT NOT NULL,           -- denormalized so reads can enforce isolation
    role         TEXT NOT NULL,           -- system | user | assistant | tool
    content_json TEXT NOT NULL,           -- full internal Message, so history replays exactly
    created_at   REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_session
    ON messages (session_id, created_at);
