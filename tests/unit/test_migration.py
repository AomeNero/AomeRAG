"""DB migration: legacy clean_state/ingest_state timestamp columns → updated_at."""

import aiosqlite

from aome_rag.session.db import open_db


async def test_legacy_clean_state_column_migrated(tmp_path) -> None:
    """A clean_state table created with the old `cleaned_at` column is renamed to
    `updated_at` on open, preserving data (otherwise save_all fails and incremental
    clean re-processes everything)."""
    path = str(tmp_path / "s.db")
    db = await aiosqlite.connect(path)
    await db.execute(
        "CREATE TABLE clean_state (path TEXT PRIMARY KEY, content_hash TEXT NOT NULL, "
        "cleaned_at REAL NOT NULL)"
    )
    await db.execute(
        "INSERT INTO clean_state (path, content_hash, cleaned_at) VALUES ('a.md', 'h', 1)"
    )
    await db.commit()
    await db.close()

    db = await open_db(path)
    try:
        cur = await db.execute("PRAGMA table_info(clean_state)")
        cols = {r["name"] for r in await cur.fetchall()}
        assert "updated_at" in cols and "cleaned_at" not in cols
        cur = await db.execute("SELECT path, content_hash FROM clean_state")
        row = dict(await cur.fetchone())
        assert row == {"path": "a.md", "content_hash": "h"}
        # and a write with the new schema works
        await db.execute(
            "INSERT INTO clean_state (path, content_hash, updated_at) VALUES ('b.md', 'h2', 1)"
        )
        await db.commit()
    finally:
        await db.close()
