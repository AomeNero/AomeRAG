"""技能协议 + 执行上下文（SkillContext）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from aome_rag.providers.base import ToolSchema


class EndTurn(Exception):
    """由技能（如 clarify）抛出，让 agent 循环在本轮中途干净地停止。"""


@dataclass
class SkillContext:
    """每次工具调用传给技能的上下文。`services` 是应用注入的类型化服务包
    （retriever、session_store 等）；`pending` 收集技能发出的事件。"""

    user: Any = None
    session_id: str = ""
    services: Any = None
    details: Any = None  # optional structured payload for the UI (e.g. kb_search hits)
    pending: list[Any] = field(default_factory=list)

    async def emit(self, event: Any) -> None:
        self.pending.append(event)


@runtime_checkable
class Skill(Protocol):
    name: str
    description: str
    tool_schema: ToolSchema
    system_prompt_fragment: str | None

    async def handle(self, ctx: SkillContext, **arguments: Any) -> str: ...
