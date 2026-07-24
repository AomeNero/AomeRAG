import os

import pytest

from aome_rag.retrieval.store import ZvecStore

pytestmark = pytest.mark.integration


def _chunk(cid, src, vec):
    return {
        "id": cid,
        "dense": vec,
        "text": f"text of {cid}",
        "source_doc": src,
        "heading_path": "",
        "page": None,
        "chunk_index": int(cid.split("#")[1]),
    }


def test_delete_by_source_removes_only_that_source(tmp_path) -> None:
    store = ZvecStore(os.path.join(str(tmp_path), "col"), dim=4)
    store.upsert_chunks(
        [
            _chunk("a.md#0", "a.md", [0.1, 0.1, 0.1, 0.1]),
            _chunk("a.md#1", "a.md", [0.2, 0.2, 0.2, 0.2]),
            _chunk("b.md#0", "b.md", [0.9, 0.9, 0.9, 0.9]),
        ]
    )
    store.delete_by_source("a.md")
    got = store.fetch_ids(["a.md#0", "a.md#1", "b.md#0"])
    assert "a.md#0" not in got and "a.md#1" not in got
    assert "b.md#0" in got


def test_delete_by_source_with_spaces_and_cjk(tmp_path) -> None:
    store = ZvecStore(os.path.join(str(tmp_path), "col"), dim=4)
    src = "1.1 GI328系列规格书.md"
    # id must be Zvec-safe (no CJK/spaces); source_doc field carries the CJK value.
    store.upsert_chunks([_chunk("cjk#0", src, [0.1, 0.2, 0.3, 0.4])])
    store.delete_by_source(src)
    assert "cjk#0" not in store.fetch_ids(["cjk#0"])
