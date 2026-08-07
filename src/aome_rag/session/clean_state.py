"""clean_state 侧表：记录 raw 文件内容哈希，支持增量清洗。"""

from __future__ import annotations

import time

import aiosqlite

from .db import write_with_retry


class CleanStateStore:
    """通用的 {path: content_hash} 状态表，按表名参数化。
    同时用于增量清洗（clean_state）和增量入库（ingest_state）。"""

    def __init__(self, db: aiosqlite.Connection, table: str = "clean_state") -> None:
        self._db = db
        self._table = table  # internal constant ("clean_state" / "ingest_state"), not user input

    async def load(self) -> dict[str, str]:
        """上次运行的 {相对路径: content_hash}。"""
        cur = await self._db.execute(f"SELECT path, content_hash FROM {self._table}")
        return {r["path"]: r["content_hash"] for r in await cur.fetchall()}

    async def save_all(self, state: dict[str, str]) -> None:
        """整体替换该表（不再存在/失败的文件被丢弃）。"""
        now = time.time()
        rows = [(p, h, now) for p, h in state.items()]

        async def _do() -> None:
            await self._db.execute(f"DELETE FROM {self._table}")
            await self._db.executemany(
                f"INSERT INTO {self._table} (path, content_hash, updated_at) VALUES (?, ?, ?)",
                rows,
            )
            await self._db.commit()

        await write_with_retry(self._db, _do)

    async def clear(self) -> None:
        async def _do() -> None:
            await self._db.execute(f"DELETE FROM {self._table}")
            await self._db.commit()

        await write_with_retry(self._db, _do)
