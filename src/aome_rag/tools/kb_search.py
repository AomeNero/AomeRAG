"""kb_search 技能——混合检索知识库（经 services.retriever）。"""

from __future__ import annotations

from typing import Any

from aome_rag.providers.base import ToolSchema
from aome_rag.tools.base import SkillContext


class KbSearchSkill:
    name = "kb_search"
    description = (
        "Retrieve relevant passages from the company knowledge base. Call this BEFORE "
        "answering, and again with different wording if the first results are weak."
    )
    tool_schema: ToolSchema = {
        "type": "function",
        "function": {
            "name": "kb_search",
            "description": "Search the knowledge base. Returns ranked passages with their source.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "natural-language search query"},
                    "top_k": {"type": "integer", "description": "max passages to return"},
                },
                "required": ["query"],
            },
        },
    }
    system_prompt_fragment = (
        "Skill `kb_search`: retrieves KB passages. Ground every factual answer in its results "
        "and cite source_doc. If results miss the point, retry with rephrased query."
    )

    async def handle(self, ctx: SkillContext, *, query: str, top_k: int | None = None) -> str:
        retriever = getattr(ctx.services, "retriever", None) if ctx.services else None
        if retriever is None:
            return "kb_search unavailable: no retriever configured."
        hits = await retriever.search(query, top_k=top_k)
        if not hits:
            return "No relevant documents found for that query."
        # 给 UI 的结构化命中（模型仍读下面的格式化字符串）
        ctx.details = [
            {
                "source_doc": h.source_doc,
                "heading_path": h.heading_path,
                "page": h.page,
                "score": h.score,
                "text": h.text,
            }
            for h in hits
        ]
        return _format_hits(hits)


def _format_hits(hits: list[Any]) -> str:
    parts: list[str] = []
    for i, h in enumerate(hits, 1):
        src = getattr(h, "source_doc", "?")
        heading = getattr(h, "heading_path", "") or ""
        page = getattr(h, "page", None)
        text = getattr(h, "text", "") or ""
        loc = f"[{i}] source={src}"
        if heading:
            loc += f" > {heading}"
        if page is not None:
            loc += f" (p.{page})"
        parts.append(f"{loc}\n{text}")
    return "\n\n".join(parts)
