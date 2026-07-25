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
        "Skill `clarify`：当问题不清或缺关键信息时调用。每次只问【一个】最关键、最聚焦的问题"
        "（不要一次列多个）；问完即停，等用户回答后再继续。绝不臆测、绝不在不清时调用 kb_search。"
    )

    async def handle(self, ctx: SkillContext, *, question: str) -> str:
        await ctx.emit(ClarifyEvent(question=question))
        raise EndTurn()
