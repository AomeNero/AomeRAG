"""POST /ingest/dir end-to-end (SSE): recursive scan, .md direct, unsupported skipped, summary."""

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


def test_ingest_dir_recursive_with_skip(tmp_path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "a.md").write_text("# A\n\nalpha beta gamma delta\n", encoding="utf-8")
    (raw / "sub").mkdir()
    (raw / "sub" / "b.md").write_text("# B\n\ndelta epsilon zeta\n", encoding="utf-8")
    (raw / "img.png").write_bytes(b"\x89PNG")  # unsupported -> skipped

    settings = Settings(
        md_data_dir=str(raw),
        sqlite_path=str(tmp_path / "s.db"),
        zvec_path=str(tmp_path / "col"),
        skills_dir=str(tmp_path / "sk"),
        embed_dim=8,
    )
    app = create_app(
        settings=settings,
        overrides={"provider": FakeProvider(), "embedder": _FakeEmbedder(8), "skills": _real_skills()},
    )

    with TestClient(app) as client:
        with client.stream("POST", "/ingest/dir", headers={"X-User-Id": "alice"}) as resp:
            assert resp.status_code == 200
            events = _sse_events(resp)

    types = [e["type"] for e in events]
    assert types[0] == "scan"
    assert events[0]["n_files"] == 2 and events[0]["n_skipped"] == 1
    assert "skipped" in types  # img.png
    assert types[-1] == "summary"

    summary = events[-1]
    assert summary["n_docs"] == 2
    assert summary["n_chunks"] >= 2
    assert summary["n_failed"] == 0

    sources = [e["source_doc"] for e in events if e["type"] == "file_done"]
    assert "a.md" in sources and "sub/b.md" in sources  # recursive


def test_ingest_dir_requires_auth(tmp_path) -> None:
    settings = Settings(
        md_data_dir=str(tmp_path / "raw"),
        sqlite_path=str(tmp_path / "s.db"),
        zvec_path=str(tmp_path / "col"),
        skills_dir=str(tmp_path / "sk"),
        embed_dim=8,
    )
    app = create_app(settings=settings, overrides={"provider": FakeProvider(), "skills": _real_skills()})
    with TestClient(app) as client:
        r = client.post("/ingest/dir")
    assert r.status_code == 401
