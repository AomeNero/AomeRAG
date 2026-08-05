"""Side table tracking chunk metadata for the admin KB manager.

zvec can't enumerate docs/chunks (only query/fetch/delete_by_filter/stats), so the
「知识库管理」page is driven by this table. It mirrors what was actually ingested:
the ingestion pipeline writes rows on ingest (delete-then-insert per source doc) and
removes them on delete — keeping it in step with the zvec collection.

All calls are async on the shared aiosqlite connection (WAL mode).
"""

from __future__ import annotations

import aiosqlite

from .db import write_with_retry


class ChunkMetaStore:
    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def replace_source(self, source_doc: str, chunks: list[dict]) -> None:
        """Rewrite all meta rows for one source doc (mirrors ingest's delete-then-insert).
        Each chunk dict needs: id, chunk_index, heading_path, text_preview, created_at."""
        rows = [
            (
                c["id"],
                source_doc,
                c.get("chunk_index", 0),
                c.get("heading_path", ""),
                c.get("text_preview", ""),
                c.get("created_at", 0),
            )
            for c in chunks
        ]

        async def _do() -> None:
            await self._db.execute("DELETE FROM chunk_meta WHERE source_doc=?", (source_doc,))
            if rows:
                await self._db.executemany(
                    "INSERT OR REPLACE INTO chunk_meta "
                    "(id, source_doc, chunk_index, heading_path, text_preview, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    rows,
                )
            await self._db.commit()

        await write_with_retry(self._db, _do)

    async def delete_source(self, source_doc: str) -> None:
        async def _do() -> None:
            await self._db.execute("DELETE FROM chunk_meta WHERE source_doc=?", (source_doc,))
            await self._db.commit()

        await write_with_retry(self._db, _do)

    async def delete_chunk(self, chunk_id: str) -> None:
        async def _do() -> None:
            await self._db.execute("DELETE FROM chunk_meta WHERE id=?", (chunk_id,))
            await self._db.commit()

        await write_with_retry(self._db, _do)

    async def chunks_for_source(self, source_doc: str) -> list[dict]:
        cur = await self._db.execute(
            "SELECT id, source_doc, chunk_index, heading_path, text_preview, created_at "
            "FROM chunk_meta WHERE source_doc=? ORDER BY chunk_index",
            (source_doc,),
        )
        return [dict(r) for r in await cur.fetchall()]

    async def source_counts(self) -> dict[str, int]:
        """{source_doc: chunk_count} for every doc that currently has chunks recorded."""
        cur = await self._db.execute(
            "SELECT source_doc, COUNT(*) AS n FROM chunk_meta GROUP BY source_doc"
        )
        return {r["source_doc"]: r["n"] for r in await cur.fetchall()}

    async def clear(self) -> None:
        async def _do() -> None:
            await self._db.execute("DELETE FROM chunk_meta")
            await self._db.commit()

        await write_with_retry(self._db, _do)
