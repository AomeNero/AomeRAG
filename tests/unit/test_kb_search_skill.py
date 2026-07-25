from dataclasses import dataclass

from aome_rag.services import Services
from aome_rag.tools.base import SkillContext
from aome_rag.tools.kb_search import KbSearchSkill


@dataclass
class _Hit:
    chunk_id: str
    score: float
    text: str
    source_doc: str
    heading_path: str
    page: int | None
    chunk_index: int


class _FakeRetriever:
    def __init__(self, hits):
        self._hits = hits
        self.last_query = None
        self.last_top_k = None

    async def search(self, query, top_k=None):
        self.last_query = query
        self.last_top_k = top_k
        return self._hits


async def test_kb_search_formats_hits_and_passes_args() -> None:
    hits = [_Hit("c1", 0.9, "the answer is 42", "spec.md", "Section 1", 3, 0)]
    retriever = _FakeRetriever(hits)
    skill = KbSearchSkill()
    ctx = SkillContext(services=Services(retriever=retriever))

    out = await skill.handle(ctx, query="meaning?", top_k=5)

    assert retriever.last_query == "meaning?"
    assert retriever.last_top_k == 5
    assert "source=spec.md" in out
    assert "Section 1" in out
    assert "p.3" in out
    assert "the answer is 42" in out


async def test_kb_search_no_retriever() -> None:
    skill = KbSearchSkill()
    ctx = SkillContext(services=None)
    out = await skill.handle(ctx, query="x")
    assert "no retriever" in out.lower()


async def test_kb_search_empty_results() -> None:
    retriever = _FakeRetriever([])
    skill = KbSearchSkill()
    ctx = SkillContext(services=Services(retriever=retriever))
    out = await skill.handle(ctx, query="x")
    assert "No relevant" in out
