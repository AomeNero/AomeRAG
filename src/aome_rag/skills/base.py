"""Skill protocol + execution context."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from aome_rag.providers.base import ToolSchema


class EndTurn(Exception):
    """Raised by a skill (e.g. clarify) to stop the agent loop cleanly mid-turn."""


@dataclass
class SkillContext:
    """Per-tool-call context handed to a skill. `services` is a typed bag (retriever,
    session_store, ...) injected by the app; `pending` collects events the skill emits."""

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
