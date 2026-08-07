"""SessionStore —— 按用户隔离的会话历史。每个读都按 user_id 限定。"""

from __future__ import annotations

import time
import uuid
from typing import Any

import aiosqlite
import structlog

from aome_rag.providers.messages import Message

from .db import write_with_retry
from .models import SessionMeta

_log = structlog.get_logger()


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

        async def _do() -> None:
            await self._db.execute(
                "INSERT INTO sessions(id, user_id, title, created_at, updated_at) VALUES (?,?,?,?,?)",
                (sid, user_id, title, now, now),
            )
            await self._db.commit()

        await write_with_retry(self._db, _do)
        _log.info("session.created", session_id=sid, user_id=user_id)
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

    async def get_messages_admin(
        self, session_id: str, limit: int = 100
    ) -> list[Message]:
        """管理端：获取任意会话的消息（不按用户限定）。"""
        rows = await self._fetchall(
            "SELECT content_json FROM messages "
            "WHERE session_id=? ORDER BY created_at LIMIT ?",
            (session_id, limit),
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

        async def _do() -> None:
            await self._db.execute(
                "INSERT INTO messages(id, session_id, user_id, role, content_json, created_at) "
                "VALUES (?,?,?,?,?,?)",
                (mid, session_id, user_id, msg.role, msg.model_dump_json(), now),
            )
            await self._db.execute(
                "UPDATE sessions SET updated_at=? WHERE id=?", (now, session_id)
            )
            await self._db.commit()

        await write_with_retry(self._db, _do)
        _log.info("session.message", session_id=session_id, role=msg.role)

    async def list_all_sessions(self, limit: int = 200, offset: int = 0) -> list[dict[str, Any]]:
        """管理端：列出所有用户的会话（不按用户限定）。"""
        rows = await self._fetchall(
            "SELECT id, user_id, title, created_at, updated_at FROM sessions "
            "ORDER BY updated_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        return [
            {
                "id": r["id"],
                "user_id": r["user_id"],
                "title": r["title"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
            }
            for r in rows
        ]

    async def submit_feedback(self, data: dict[str, Any]) -> str:
        """插入一条反馈记录。返回反馈 id。"""
        fid = uuid.uuid4().hex

        async def _do() -> None:
            await self._db.execute(
                "INSERT INTO feedback(id, type, session_id, user_id, message_id, rating, "
                "user_question, ai_answer, comment, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    fid,
                    data.get("type", ""),
                    data.get("session_id"),
                    data.get("user_id", ""),
                    data.get("message_id"),
                    data.get("rating"),
                    data.get("user_question"),
                    data.get("ai_answer"),
                    data.get("comment"),
                    time.time(),
                ),
            )
            await self._db.commit()

        await write_with_retry(self._db, _do)
        return fid

    async def list_all_feedback(self, limit: int = 200) -> list[dict[str, Any]]:
        """管理端：列出所有用户的反馈。"""
        rows = await self._fetchall(
            "SELECT id, type, session_id, user_id, message_id, rating, "
            "user_question, ai_answer, comment, created_at "
            "FROM feedback ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        return [dict(r) for r in rows]

    async def delete_feedback(self, feedback_id: str) -> bool:
        async def _do() -> None:
            await self._db.execute("DELETE FROM feedback WHERE id=?", (feedback_id,))
            await self._db.commit()

        await write_with_retry(self._db, _do)
        _log.info("session.feedback", feedback_id=fid, feedback_type=data.get("type"))
        return True

    async def delete_session(self, session_id: str, user_id: str) -> bool:
        row = await self._fetchone(
            "SELECT user_id FROM sessions WHERE id=?", (session_id,)
        )
        if row is None or row["user_id"] != user_id:
            return False

        async def _do() -> None:
            await self._db.execute("DELETE FROM messages WHERE session_id=?", (session_id,))
            await self._db.execute("DELETE FROM sessions WHERE id=?", (session_id,))
            await self._db.commit()

        await write_with_retry(self._db, _do)
        _log.info("session.deleted", session_id=session_id)
        return True

    async def set_title(self, session_id: str, user_id: str, title: str) -> bool:
        """设置/重命名会话标题。找不到或无权时返回 False。"""
        row = await self._fetchone(
            "SELECT user_id FROM sessions WHERE id=?", (session_id,)
        )
        if row is None or row["user_id"] != user_id:
            return False

        async def _do() -> None:
            await self._db.execute(
                "UPDATE sessions SET title=?, updated_at=? WHERE id=?",
                (title, time.time(), session_id),
            )
            await self._db.commit()

        await write_with_retry(self._db, _do)
        return True

    async def search_messages(
        self, user_id: str, q: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        """在用户的消息文本 + 会话标题里做关键词搜索（SQL LIKE）。
        返回命中，含首个匹配附近的片段。"""
        like = f"%{q}%"
        rows = await self._fetchall(
            "SELECT m.session_id, m.role, m.content_json, s.title "
            "FROM messages m JOIN sessions s ON m.session_id = s.id "
            "WHERE m.user_id = ? AND (m.content_json LIKE ? OR s.title LIKE ?) "
            "ORDER BY m.created_at DESC LIMIT ?",
            (user_id, like, like, limit),
        )
        needle = q.lower()
        results: list[dict[str, Any]] = []
        for r in rows:
            text = Message.model_validate_json(r["content_json"]).as_text()
            idx = text.lower().find(needle)
            start = max(0, idx - 30) if idx >= 0 else 0
            end = (idx + len(q) + 60) if idx >= 0 else 60
            snippet = text[start:end]
            results.append(
                {
                    "session_id": r["session_id"],
                    "title": r["title"] or "新对话",
                    "role": r["role"],
                    "snippet": snippet,
                }
            )
        return results
