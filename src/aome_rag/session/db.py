"""SQLite 连接工厂：WAL 模式 + busy_timeout。"""

from __future__ import annotations

import asyncio
import sqlite3
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

CREATE TABLE IF NOT EXISTS chunk_meta (
    id           TEXT PRIMARY KEY,
    source_doc   TEXT NOT NULL,
    chunk_index  INTEGER NOT NULL,
    heading_path TEXT NOT NULL DEFAULT '',
    text_preview TEXT NOT NULL DEFAULT '',
    created_at   REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunk_meta_source ON chunk_meta (source_doc, chunk_index);

CREATE TABLE IF NOT EXISTS clean_state (
    path         TEXT PRIMARY KEY,
    content_hash TEXT NOT NULL,
    updated_at   REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS ingest_state (
    path         TEXT PRIMARY KEY,
    content_hash TEXT NOT NULL,
    updated_at   REAL NOT NULL
);
"""


async def open_db(path: str) -> aiosqlite.Connection:
    parent = Path(path).parent
    parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(path)
    db.row_factory = aiosqlite.Row
    for pragma in _PRAGMAS:
        await db.execute(pragma)
    await db.executescript(_SCHEMA)
    await _migrate_state_columns(db)
    return db


async def _migrate_state_columns(db: aiosqlite.Connection) -> None:
    """把旧版状态表的时间戳列（`cleaned_at` / `ingested_at`）规范成
    `updated_at`。`CREATE TABLE IF NOT EXISTS` 不会改已有表，所以改名前的表
    保留旧列，否则每次写入都会失败。"""
    for table in ("clean_state", "ingest_state"):
        cur = await db.execute(f"PRAGMA table_info({table})")
        cols = {r["name"] for r in await cur.fetchall()}
        if "updated_at" not in cols:
            for old in ("cleaned_at", "ingested_at"):
                if old in cols:
                    await db.execute(f"ALTER TABLE {table} RENAME COLUMN {old} TO updated_at")
                    break
    await db.commit()


async def write_with_retry(
    db: aiosqlite.Connection, fn, retries: int = 3, delay: float = 1.0
) -> None:
    """稳健地执行一次数据库写入（`fn` 执行语句并提交）：
    任何出错都回滚，失败的写绝不会泄漏未关闭的事务
    （否则会占用写锁、让后续写入全部失败），并对瞬时的
    `database is locked` 重试几次。"""
    for attempt in range(retries):
        try:
            await fn()
            return
        except sqlite3.OperationalError as e:
            await db.rollback()
            if "locked" in str(e).lower() and attempt < retries - 1:
                await asyncio.sleep(delay)
                continue
            raise
