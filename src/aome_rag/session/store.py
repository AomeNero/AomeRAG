"""SessionStore — per-user conversation history. Every read is scoped by user_id so
isolation is enforced at the data layer (a user can never read another's session)."""

from __future__ import annotations

import time
import uuid
from typing import Any

import aiosqlite

from aome_rag.providers.messages import Message

from .models import SessionMeta


class SessionNotFound(KeyError):
    pass


class SessionStore:
    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def _fetchone(self, sql: str, params: tuple = ()) -> Any:
        cur = await self._db.execute(sql, params)
        row = await cur.fetchone()
        await cur.close()
        return row

    async def _fetchall(self, sql: str, params: tuple = ()) -> list[Any]:
        cur = await self._db.execute(sql, params)
        rows = await cur.fetchall()
        await cur.close()
        return rows

    async def list_sessions(
        self, user_id: str, limit: int = 50, offset: int = 0
    ) -> list[SessionMeta]:
        rows = await self._fetchall(
            "SELECT id, title, created_at, updated_at FROM sessions "
            "WHERE user_id=? ORDER BY updated_at DESC LIMIT ? OFFSET ?",
            (user_id, limit, offset),
        )
        return [
            SessionMeta(r["id"], r["title"], r["created_at"], r["updated_at"]) for r in rows
        ]

    async def create_session(self, user_id: str, title: str | None = None) -> str:
        sid = uuid.uuid4().hex
        now = time.time()
        await self._db.execute(
            "INSERT INTO sessions(id, user_id, title, created_at, updated_at) VALUES (?,?,?,?,?)",
            (sid, user_id, title, now, now),
        )
        await self._db.commit()
        return sid

    async def get_messages(
        self, session_id: str, user_id: str, limit: int = 100
    ) -> list[Message]:
        rows = await self._fetchall(
            "SELECT m.content_json FROM messages m "
            "JOIN sessions s ON m.session_id = s.id "
            "WHERE m.session_id=? AND s.user_id=? ORDER BY m.created_at LIMIT ?",
            (session_id, user_id, limit),
        )
        return [Message.model_validate_json(r["content_json"]) for r in rows]

    async def append_message(
        self, session_id: str, user_id: str, msg: Message
    ) -> None:
        row = await self._fetchone(
            "SELECT user_id FROM sessions WHERE id=?", (session_id,)
        )
        if row is not None and row["user_id"] != user_id:
            raise SessionNotFound(session_id)  # do not leak cross-user existence
        now = time.time()
        if row is None:
            await self._db.execute(
                "INSERT INTO sessions(id, user_id, title, created_at, updated_at) "
                "VALUES (?,?,?,?,?)",
                (session_id, user_id, None, now, now),
            )
        mid = uuid.uuid4().hex
        await self._db.execute(
            "INSERT INTO messages(id, session_id, user_id, role, content_json, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (mid, session_id, user_id, msg.role, msg.model_dump_json(), now),
        )
        await self._db.execute(
            "UPDATE sessions SET updated_at=? WHERE id=?", (now, session_id)
        )
        await self._db.commit()

    async def delete_session(self, session_id: str, user_id: str) -> bool:
        row = await self._fetchone(
            "SELECT user_id FROM sessions WHERE id=?", (session_id,)
        )
        if row is None or row["user_id"] != user_id:
            return False
        await self._db.execute("DELETE FROM messages WHERE session_id=?", (session_id,))
        await self._db.execute("DELETE FROM sessions WHERE id=?", (session_id,))
        await self._db.commit()
        return True
