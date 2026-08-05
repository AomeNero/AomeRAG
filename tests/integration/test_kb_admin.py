"""KB management endpoints (/admin/kb/*) end-to-end against a real local Zvec + fake embedder."""

import json

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


def _make_app(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "a.md").write_text(
        "# Alpha\n\nalpha beta gamma delta\n\n## Detail\n\nmore text here\n", encoding="utf-8"
    )
    (raw / "b.md").write_text("# Beta\n\nbeta gamma delta epsilon\n", encoding="utf-8")
    settings = Settings(
        md_data_dir=str(raw),
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


def _ingest_all(client) -> None:
    with client.stream("POST", "/ingest/dir", headers={"X-User-Id": "admin"}) as resp:
        events = _sse_events(resp)
    assert events[-1]["n_failed"] == 0
    assert events[-1]["n_docs"] == 2


def _doc_item(client, source_doc: str) -> dict:
    body = client.get("/admin/kb/docs", headers={"X-User-Id": "admin"}).json()
    return next(i for i in body["items"] if i["source_doc"] == source_doc)


def test_kb_docs_list_and_chunks(tmp_path) -> None:
    app = _make_app(tmp_path)
    with TestClient(app) as client:
        _ingest_all(client)
        r = client.get("/admin/kb/docs", headers={"X-User-Id": "admin"})
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 2
        items = {i["source_doc"]: i for i in body["items"]}
        assert items["a.md"]["status"] == "ok"
        assert items["a.md"]["file_exists"] is True
        assert items["a.md"]["n_chunks"] >= 1

        c = client.get("/admin/kb/chunks", params={"source_doc": "a.md"}, headers={"X-User-Id": "admin"})
        assert c.status_code == 200
        chunks = c.json()["chunks"]
        assert len(chunks) == items["a.md"]["n_chunks"]
        assert chunks[0]["text_preview"] and chunks[0]["heading_path"] != ""


def test_kb_delete_single_chunk(tmp_path) -> None:
    app = _make_app(tmp_path)
    with TestClient(app) as client:
        _ingest_all(client)
        chunks = client.get(
            "/admin/kb/chunks", params={"source_doc": "a.md"}, headers={"X-User-Id": "admin"}
        ).json()["chunks"]
        cid = chunks[0]["id"]
        r = client.delete("/admin/kb/chunk", params={"id": cid}, headers={"X-User-Id": "admin"})
        assert r.status_code == 200
        remaining = client.get(
            "/admin/kb/chunks", params={"source_doc": "a.md"}, headers={"X-User-Id": "admin"}
        ).json()["chunks"]
        assert len(remaining) == len(chunks) - 1
        assert cid not in [c["id"] for c in remaining]


def test_kb_delete_doc_chunks_and_file(tmp_path) -> None:
    app = _make_app(tmp_path)
    with TestClient(app) as client:
        _ingest_all(client)
        r = client.delete("/admin/kb/doc-chunks", params={"source_doc": "a.md"}, headers={"X-User-Id": "admin"})
        assert r.status_code == 200
        a = _doc_item(client, "a.md")
        assert a["n_chunks"] == 0 and a["file_exists"] is True and a["status"] == "unsliced"
        assert (tmp_path / "raw" / "a.md").exists()  # file untouched

        r = client.delete("/admin/kb/file", params={"source_doc": "a.md"}, headers={"X-User-Id": "admin"})
        assert r.status_code == 200
        assert not (tmp_path / "raw" / "a.md").exists()
        items = client.get("/admin/kb/docs", headers={"X-User-Id": "admin"}).json()["items"]
        assert all(i["source_doc"] != "a.md" for i in items)  # gone from list (no file, no chunks)


def test_kb_orphan_detection(tmp_path) -> None:
    app = _make_app(tmp_path)
    with TestClient(app) as client:
        _ingest_all(client)
        client.delete("/admin/kb/file", params={"source_doc": "b.md"}, headers={"X-User-Id": "admin"})
        b = _doc_item(client, "b.md")
        assert b["status"] == "orphan" and b["n_chunks"] >= 1 and b["file_exists"] is False
        # filter=orphan narrows the list
        body = client.get("/admin/kb/docs", params={"filter": "orphan"}, headers={"X-User-Id": "admin"}).json()
        assert [i["source_doc"] for i in body["items"]] == ["b.md"]


def test_kb_reingest_and_sync(tmp_path) -> None:
    app = _make_app(tmp_path)
    with TestClient(app) as client:
        _ingest_all(client)
        r = client.post("/admin/kb/reingest", params={"source_doc": "a.md"}, headers={"X-User-Id": "admin"})
        assert r.status_code == 200
        assert r.json()["n_chunks"] >= 1

        # sync rebuilds the side table from md-data (verifying against zvec)
        body = client.post("/admin/kb/sync", headers={"X-User-Id": "admin"}).json()
        assert body["ok"] is True
        assert body["n_docs"] >= 1 and body["n_chunks"] >= 1

        # after resetting the vector store, sync records nothing (chunks no longer in zvec)
        client.post("/admin/reset", headers={"X-User-Id": "admin"})
        body = client.post("/admin/kb/sync", headers={"X-User-Id": "admin"}).json()
        assert body["n_chunks"] == 0


def test_kb_admin_requires_auth(tmp_path) -> None:
    app = _make_app(tmp_path)
    with TestClient(app) as client:
        assert client.get("/admin/kb/docs").status_code == 401
        assert client.delete("/admin/kb/file", params={"source_doc": "a.md"}).status_code == 401
