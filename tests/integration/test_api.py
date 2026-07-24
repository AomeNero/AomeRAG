"""Phase 7 API integration: SSE chat, session CRUD/isolation, ingest endpoint.

Uses create_app(overrides=...) to inject a FakeProvider + fakes, while the lifespan still
builds the real SQLite session DB and Zvec store at temp paths."""

import json

import pytest
from fastapi.testclient import TestClient

from aome_rag.config import Settings
from aome_rag.main import create_app
from aome_rag.providers.base import Finish, TextDelta, ToolCallDelta
from aome_rag.retrieval.embedder import OllamaEmbedder
from aome_rag.retrieval.retriever import Hit
from aome_rag.skills.clarify import ClarifySkill
from aome_rag.skills.kb_search import KbSearchSkill
from aome_rag.skills.registry import SkillRegistry

from tests.fakes import FakeProvider

pytestmark = pytest.mark.integration


def _real_skills() -> SkillRegistry:
    reg = SkillRegistry()
    reg.register(KbSearchSkill())
    reg.register(ClarifySkill())
    return reg


class _FakeRetriever:
    async def search(self, query, top_k=None, filters=None):
        return [
            Hit("ops.md#0", 0.9, "deploy via github actions on every commit", "ops.md", "Deploy", 1, 0)
        ]


class _FakeEmbedder(OllamaEmbedder):
    def __init__(self, dim: int) -> None:
        self._dim = dim

    async def embed_batch(self, texts):
        return [[0.1] * self._dim for _ in texts]

    async def embed(self, text):
        return [0.1] * self._dim


@pytest.fixture
def build_app(tmp_path):
    def _build(*, provider: FakeProvider, retriever=None, embedder=None, skills=None) -> tuple:
        settings = Settings(
            sqlite_path=str(tmp_path / "s.db"),
            zvec_path=str(tmp_path / "col"),
            skills_dir=str(tmp_path / "skills"),
            embed_dim=8,  # match _FakeEmbedder(8)
        )
        overrides: dict = {"provider": provider, "skills": skills or _real_skills()}
        if retriever is not None:
            overrides["retriever"] = retriever
        if embedder is not None:
            overrides["embedder"] = embedder
        return create_app(settings=settings, overrides=overrides)

    return _build


def test_chat_nonstream_final_answer_persists(build_app) -> None:
    provider = FakeProvider()
    provider.enqueue([TextDelta(text="hi there"), Finish(finish_reason="stop")])
    app = build_app(provider=provider)
    with TestClient(app) as client:
        r = client.post(
            "/chat", json={"message": "hello", "stream": False}, headers={"X-User-Id": "alice"}
        )
        assert r.status_code == 200
        body = r.json()
        assert body["answer"] == "hi there"
        sid = body["session_id"]

        msgs = client.get(f"/sessions/{sid}/messages", headers={"X-User-Id": "alice"}).json()
        assert [m["role"] for m in msgs] == ["user", "assistant"]


def test_chat_sse_kb_search(build_app) -> None:
    provider = FakeProvider()
    provider.enqueue(
        [
            ToolCallDelta(index=0, id="call_1", name="kb_search", arguments_chunk='{"query": "deploy"}'),
            Finish(finish_reason="tool_calls"),
        ]
    )
    provider.enqueue([TextDelta(text="found it"), Finish(finish_reason="stop")])
    app = build_app(provider=provider, retriever=_FakeRetriever())

    with TestClient(app) as client:
        with client.stream(
            "POST", "/chat", json={"message": "how deploy?", "stream": True}, headers={"X-User-Id": "alice"}
        ) as resp:
            events = [
                json.loads(line[5:].strip())
                for line in resp.iter_lines()
                if line.startswith("data:")
            ]

    types = [e["type"] for e in events]
    assert types[0] == "session"
    assert "tool_start" in types and "tool_result" in types
    assert types[-1] == "final"
    tool_result = next(e for e in events if e["type"] == "tool_result")
    assert "ops.md" in tool_result["content"]


def test_session_isolation_across_users(build_app) -> None:
    app = build_app(provider=FakeProvider())
    with TestClient(app) as client:
        c = client.post("/sessions", json={"title": "t"}, headers={"X-User-Id": "alice"})
        sid = c.json()["id"]
        alice = client.get("/sessions", headers={"X-User-Id": "alice"}).json()
        bob = client.get("/sessions", headers={"X-User-Id": "bob"}).json()
        assert any(s["id"] == sid for s in alice)
        assert all(s["id"] != sid for s in bob)  # bob cannot see alice's session


def test_ingest_endpoint(build_app) -> None:
    provider = FakeProvider()  # unused by ingest
    app = build_app(provider=provider, embedder=_FakeEmbedder(8))
    md = b"# Deploy\n\ndeploy with github actions on every commit.\n"
    with TestClient(app) as client:
        r = client.post(
            "/ingest",
            files={"files": ("ops.md", md, "text/markdown")},
            headers={"X-User-Id": "alice"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["n_docs"] == 1
    assert body["n_chunks"] >= 1
    assert body["n_failed"] == 0


def test_chat_requires_auth(build_app) -> None:
    app = build_app(provider=FakeProvider())
    with TestClient(app) as client:
        r = client.post("/chat", json={"message": "hi", "stream": False})
    assert r.status_code == 401
