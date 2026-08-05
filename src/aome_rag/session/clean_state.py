"""clean_state side table: per-raw-file content hashes from the last incremental clean.

The 增量更新 flow hashes every raw file and compares against this table to decide
which documents are new/modified (re-clean + re-ingest) vs unchanged (skip).
"""

from __future__ import annotations

import time

import aiosqlite

from .db import write_with_retry


class CleanStateStore:
    """Generic {path: content_hash} state table, parametrized by table name.
    Used for both incremental clean (clean_state) and incremental ingest (ingest_state)."""

    def __init__(self, db: aiosqlite.Connection, table: str = "clean_state") -> None:
        self._db = db
        self._table = table  # internal constant ("clean_state" / "ingest_state"), not user input

    async def load(self) -> dict[str, str]:
        """{relative path: content_hash} from the last run."""
        cur = await self._db.execute(f"SELECT path, content_hash FROM {self._table}")
        return {r["path"]: r["content_hash"] for r in await cur.fetchall()}

    async def save_all(self, state: dict[str, str]) -> None:
        """Replace the whole table (files no longer present / failed are dropped)."""
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
