"""ChunkMetaStore side table: the data source behind the /admin/kb management page."""

from aome_rag.session.chunk_meta import ChunkMetaStore
from aome_rag.session.db import open_db


async def test_replace_source_and_queries(tmp_path) -> None:
    db = await open_db(str(tmp_path / "s.db"))
    store = ChunkMetaStore(db)
    try:
        await store.replace_source(
            "a.md",
            [
                {"id": "x#0", "chunk_index": 0, "heading_path": "H1", "text_preview": "t0", "created_at": 1},
                {"id": "x#1", "chunk_index": 1, "heading_path": "H2", "text_preview": "t1", "created_at": 1},
            ],
        )
        await store.replace_source(
            "b.md",
            [{"id": "y#0", "chunk_index": 0, "heading_path": "", "text_preview": "t", "created_at": 2}],
        )

        assert await store.source_counts() == {"a.md": 2, "b.md": 1}
        chunks = await store.chunks_for_source("a.md")
        assert [c["chunk_index"] for c in chunks] == [0, 1]
        assert chunks[0]["heading_path"] == "H1"

        # replace_source is delete-then-insert: empty list wipes the source's rows
        await store.replace_source("a.md", [])
        assert "a.md" not in await store.source_counts()
        assert await store.chunks_for_source("a.md") == []
    finally:
        await db.close()


async def test_delete_and_clear(tmp_path) -> None:
    db = await open_db(str(tmp_path / "s.db"))
    store = ChunkMetaStore(db)
    try:
        await store.replace_source(
            "a.md",
            [
                {"id": "x#0", "chunk_index": 0, "heading_path": "", "text_preview": "t", "created_at": 1},
                {"id": "x#1", "chunk_index": 1, "heading_path": "", "text_preview": "t", "created_at": 1},
            ],
        )
        await store.delete_chunk("x#0")
        assert [c["id"] for c in await store.chunks_for_source("a.md")] == ["x#1"]

        await store.delete_source("a.md")
        assert await store.source_counts() == {}

        await store.replace_source("b.md", [{"id": "y#0", "chunk_index": 0, "heading_path": "", "text_preview": "t", "created_at": 1}])
        await store.clear()
        assert await store.source_counts() == {}
    finally:
        await db.close()
