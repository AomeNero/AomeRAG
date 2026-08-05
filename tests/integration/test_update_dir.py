"""POST /update/dir incremental clean+ingest: only new/modified processed, removed dropped."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aome_rag.config import Settings
from aome_rag.main import create_app
from aome_rag.retrieval.embedder import OllamaEmbedder
from aome_rag.tools.clarify import ClarifySkill
from aome_rag.tools.kb_search import KbSearchSkill
from aome_rag.tools.registry import SkillRegistry

from tests.fakes import FakeProvider

pytestmark = pytest.mark.integration


class _FakeEmbedder(OllamaEmbedder):
    def __init__(self, dim: int) -> None:
        self._d = dim

    async def embed_batch(self, texts):
        return [[0.1] * self._d for _ in texts]


def _real_skills() -> SkillRegistry:
    reg = SkillRegistry()
    reg.register(KbSearchSkill())
    reg.register(ClarifySkill())
    return reg


def _sse_events(resp) -> list[dict]:
    return [json.loads(line[5:].strip()) for line in resp.iter_lines() if line.startswith("data:")]


def _make_app(tmp_path, raw: Path):
    settings = Settings(
        raw_data_dir=str(raw),
        md_data_dir=str(tmp_path / "md-data"),
        sqlite_path=str(tmp_path / "s.db"),
        zvec_path=str(tmp_path / "col"),
        skills_dir=str(tmp_path / "sk"),
        embed_dim=8,
    )
    return create_app(
        settings=settings,
        overrides={
            "provider": FakeProvider(),
            "embedder": _FakeEmbedder(8),
            "skills": _real_skills(),
        },
    )


def _run(client) -> list[dict]:
    with client.stream("POST", "/update/dir", headers={"X-User-Id": "admin"}) as resp:
        assert resp.status_code == 200
        return _sse_events(resp)


def _clean_summary(events: list[dict]) -> dict:
    """The clean-phase summary carries n_cleaned (the ingest summary follows it)."""
    for e in reversed(events):
        if e["type"] == "summary" and "n_cleaned" in e:
            return e
    raise AssertionError("no clean summary in events")


def test_update_incremental_new_modify_delete(tmp_path) -> None:
    raw = tmp_path / "raw-data"
    raw.mkdir()
    (raw / "a.md").write_text("# A\n\ncontent a\n", encoding="utf-8")
    md = tmp_path / "md-data"
    app = _make_app(tmp_path, raw)

    with TestClient(app) as client:
        # 1. first run: state empty → all new
        ev1 = _run(client)
        assert (md / "a.md").is_file()
        s1 = _clean_summary(ev1)
        assert s1["n_cleaned"] == 1
        assert s1["n_skipped"] == 0

        # 2. add b.md; unchanged a.md is skipped
        (raw / "b.md").write_text("# B\n\ncontent b\n", encoding="utf-8")
        ev2 = _run(client)
        assert (md / "b.md").is_file()
        s2 = _clean_summary(ev2)
        assert s2["n_cleaned"] == 1
        assert s2["n_skipped"] == 1  # a.md unchanged
        assert "deleted" not in [e["type"] for e in ev2]

        # both docs are in the vector store now
        docs = client.get("/admin/kb/docs", headers={"X-User-Id": "admin"}).json()
        assert docs["total"] == 2

        # 3. modify a.md → only a is re-processed
        (raw / "a.md").write_text("# A v2\n\nnew content a2\n", encoding="utf-8")
        ev3 = _run(client)
        assert "v2" in (md / "a.md").read_text(encoding="utf-8")
        s3 = _clean_summary(ev3)
        assert s3["n_cleaned"] == 1
        assert s3["n_skipped"] == 1  # b.md unchanged

        # 4. delete b.md → md removed + chunks dropped
        (raw / "b.md").unlink()
        ev4 = _run(client)
        assert not (md / "b.md").exists()
        s4 = _clean_summary(ev4)
        assert s4["n_deleted"] == 1
        docs = client.get("/admin/kb/docs", headers={"X-User-Id": "admin"}).json()
        assert docs["total"] == 1  # only a.md remains


def test_update_dir_requires_auth(tmp_path) -> None:
    raw = tmp_path / "raw-data"
    raw.mkdir()
    app = _make_app(tmp_path, raw)
    with TestClient(app) as client:
        assert client.post("/update/dir").status_code == 401


def _ingest_summary(events: list[dict]) -> dict:
    """The incremental-ingest summary carries n_ingested."""
    for e in reversed(events):
        if e["type"] == "summary" and "n_ingested" in e:
            return e
    raise AssertionError("no ingest summary in events")


def test_ingest_dir_inc_incremental(tmp_path) -> None:
    """Standalone 增量切片: only new/modified md re-ingested, removed chunks dropped."""
    raw = tmp_path / "raw-data"
    raw.mkdir()
    md = tmp_path / "md-data"
    md.mkdir()
    (md / "a.md").write_text("# A\n\ncontent a\n", encoding="utf-8")
    app = _make_app(tmp_path, raw)

    with TestClient(app) as client:
        # 1. first run: ingest_state empty → all new
        with client.stream("POST", "/ingest/dir/inc", headers={"X-User-Id": "admin"}) as resp:
            ev1 = _sse_events(resp)
        s1 = _ingest_summary(ev1)
        assert s1["n_ingested"] == 1
        assert s1["n_skipped"] == 0
        assert client.get("/admin/kb/docs", headers={"X-User-Id": "admin"}).json()["total"] == 1

        # 2. add b.md → only b sliced, a skipped
        (md / "b.md").write_text("# B\n\ncontent b\n", encoding="utf-8")
        with client.stream("POST", "/ingest/dir/inc", headers={"X-User-Id": "admin"}) as resp:
            ev2 = _sse_events(resp)
        s2 = _ingest_summary(ev2)
        assert s2["n_ingested"] == 1
        assert s2["n_skipped"] == 1
        assert client.get("/admin/kb/docs", headers={"X-User-Id": "admin"}).json()["total"] == 2

        # 3. modify a.md → only a re-sliced
        (md / "a.md").write_text("# A v2\n\nnew content\n", encoding="utf-8")
        with client.stream("POST", "/ingest/dir/inc", headers={"X-User-Id": "admin"}) as resp:
            ev3 = _sse_events(resp)
        assert _ingest_summary(ev3)["n_ingested"] == 1

        # 4. delete b.md → chunks dropped
        (md / "b.md").unlink()
        with client.stream("POST", "/ingest/dir/inc", headers={"X-User-Id": "admin"}) as resp:
            ev4 = _sse_events(resp)
        s4 = _ingest_summary(ev4)
        assert s4["n_deleted"] == 1
        assert client.get("/admin/kb/docs", headers={"X-User-Id": "admin"}).json()["total"] == 1


def test_ingest_dir_inc_requires_auth(tmp_path) -> None:
    raw = tmp_path / "raw-data"
    raw.mkdir()
    app = _make_app(tmp_path, raw)
    with TestClient(app) as client:
        assert client.post("/ingest/dir/inc").status_code == 401


def test_clean_dir_inc_and_clear_state(tmp_path) -> None:
    """清洗数据 is incremental clean-only; clearing clean_state forces a full clean."""
    raw = tmp_path / "raw-data"
    raw.mkdir()
    (raw / "a.md").write_text("# A\n\ncontent a\n", encoding="utf-8")
    md = tmp_path / "md-data"
    app = _make_app(tmp_path, raw)

    with TestClient(app) as client:
        # 1. first incremental clean: full (state empty)
        with client.stream("POST", "/clean/dir/inc", headers={"X-User-Id": "admin"}) as resp:
            ev1 = _sse_events(resp)
        assert (md / "a.md").is_file()
        assert _clean_summary(ev1)["n_cleaned"] == 1

        # 2. second clean: skips the unchanged file
        with client.stream("POST", "/clean/dir/inc", headers={"X-User-Id": "admin"}) as resp:
            ev2 = _sse_events(resp)
        assert _clean_summary(ev2)["n_cleaned"] == 0
        assert _clean_summary(ev2)["n_skipped"] == 1

        # 3. clear clean_state → next clean is full again
        assert client.post("/admin/kb/clean-state/clear", headers={"X-User-Id": "admin"}).status_code == 200
        with client.stream("POST", "/clean/dir/inc", headers={"X-User-Id": "admin"}) as resp:
            ev3 = _sse_events(resp)
        assert _clean_summary(ev3)["n_cleaned"] == 1


def test_ingest_state_clear_forces_full(tmp_path) -> None:
    """Clearing ingest_state makes the next 矢量化数据 re-slice everything."""
    raw = tmp_path / "raw-data"
    raw.mkdir()
    md = tmp_path / "md-data"
    md.mkdir()
    (md / "a.md").write_text("# A\n\ncontent a\n", encoding="utf-8")
    app = _make_app(tmp_path, raw)

    with TestClient(app) as client:
        with client.stream("POST", "/ingest/dir/inc", headers={"X-User-Id": "admin"}) as resp:
            ev1 = _sse_events(resp)
        assert _ingest_summary(ev1)["n_ingested"] == 1

        client.post("/admin/kb/ingest-state/clear", headers={"X-User-Id": "admin"})
        with client.stream("POST", "/ingest/dir/inc", headers={"X-User-Id": "admin"}) as resp:
            ev2 = _sse_events(resp)
        assert _ingest_summary(ev2)["n_ingested"] == 1  # full again


def test_clear_state_requires_auth(tmp_path) -> None:
    raw = tmp_path / "raw-data"
    raw.mkdir()
    app = _make_app(tmp_path, raw)
    with TestClient(app) as client:
        assert client.post("/admin/kb/clean-state/clear").status_code == 401
        assert client.post("/admin/kb/ingest-state/clear").status_code == 401


def test_clean_dir_inc_emits_file_skipped(tmp_path) -> None:
    """Already-cleaned (unchanged) docs emit a file_skipped event, not a re-clean."""
    raw = tmp_path / "raw-data"
    raw.mkdir()
    (raw / "a.md").write_text("# A\n\ncontent a\n", encoding="utf-8")
    app = _make_app(tmp_path, raw)

    with TestClient(app) as client:
        with client.stream("POST", "/clean/dir/inc", headers={"X-User-Id": "admin"}) as resp:
            ev1 = _sse_events(resp)
        assert "file_skipped" not in [e["type"] for e in ev1]  # first run cleaned it

        with client.stream("POST", "/clean/dir/inc", headers={"X-User-Id": "admin"}) as resp:
            ev2 = _sse_events(resp)
        skipped = [e for e in ev2 if e["type"] == "file_skipped"]
        assert any(e["source_doc"] == "a.md" for e in skipped)


def test_clean_dir_inc_excludes_temp_files(tmp_path) -> None:
    """Office/hidden files starting with `~` are excluded from cleaning."""
    raw = tmp_path / "raw-data"
    raw.mkdir()
    (raw / "a.md").write_text("# A\n\ncontent a\n", encoding="utf-8")
    (raw / "~$a.docx").write_bytes(b"temp")  # must be ignored
    md = tmp_path / "md-data"
    app = _make_app(tmp_path, raw)

    with TestClient(app) as client:
        with client.stream("POST", "/clean/dir/inc", headers={"X-User-Id": "admin"}) as resp:
            ev1 = _sse_events(resp)
        assert _clean_summary(ev1)["n_cleaned"] == 1  # only a.md
        assert (md / "a.md").is_file()
        assert not (md / "~$a.md").exists()  # no md generated for the temp file
        assert "~$a.docx" not in [e.get("source_doc") for e in ev1 if e["type"] == "file_done"]
