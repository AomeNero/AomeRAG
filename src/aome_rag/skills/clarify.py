"""clarify skill — ask the user a clarifying question and end the turn (no second LLM call)."""

from __future__ import annotations

from aome_rag.agent.events import ClarifyEvent
from aome_rag.providers.base import ToolSchema
from aome_rag.skills.base import EndTurn, SkillContext


class ClarifySkill:
    name = "clarify"
    description = (
        "Ask the user ONE focused clarifying question when their request is ambiguous or "
        "missing key detail. Ends your turn — wait for their reply."
    )
    tool_schema: ToolSchema = {
        "type": "function",
        "function": {
            "name": "clarify",
            "description": "Ask the user a clarifying question.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "the single clarifying question to ask the user",
                    }
                },
                "required": ["question"],
            },
        },
    }
    system_prompt_fragment = (
        "Skill `clarify`: use when the user's question is ambiguous. Ask ONE concrete question, "
        "then stop. Do NOT guess. Do NOT call kb_search before clarifying if the query is unclear."
    )

    async def handle(self, ctx: SkillContext, *, question: str) -> str:
        await ctx.emit(ClarifyEvent(question=question))
        raise EndTurn()
