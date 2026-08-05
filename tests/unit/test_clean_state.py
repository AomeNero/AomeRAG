"""CleanStateStore: per-raw-file content hashes backing the incremental clean."""

from aome_rag.session.clean_state import CleanStateStore
from aome_rag.session.db import open_db


async def test_save_load_replace_clear(tmp_path) -> None:
    db = await open_db(str(tmp_path / "s.db"))
    store = CleanStateStore(db)
    try:
        assert await store.load() == {}
        await store.save_all({"a.md": "hash1", "b.md": "hash2"})
        assert await store.load() == {"a.md": "hash1", "b.md": "hash2"}
        # save_all replaces the whole table
        await store.save_all({"a.md": "hash3"})
        assert await store.load() == {"a.md": "hash3"}
        await store.clear()
        assert await store.load() == {}
    finally:
        await db.close()
