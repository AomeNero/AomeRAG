"""The agent loop — s01 direct descendant.

Drives the provider, forwards streamed tokens, accumulates tool calls, dispatches skills,
appends to the working transcript, and yields observation events. Provider-agnostic and
skill-agnostic: it imports only `LLMProvider` and `SkillRegistry` abstractions.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from aome_rag.providers.base import Finish, LLMDelta, LLMProvider, TextDelta, ToolCallDelta
from aome_rag.providers.errors import ToolCallParseError
from aome_rag.providers.messages import Message, TextBlock, ToolResultBlock, ToolUseBlock

from .context import assemble_system_prompt
from .events import (
    ErrorEvent,
    FinalEvent,
    StreamEvent,
    TokenEvent,
    ToolResultEvent,
    ToolStartEvent,
)
from ..providers.openai_compat import parse_tool_arguments
from ..skills.base import EndTurn, SkillContext
from ..skills.registry import SkillRegistry


class AgentLoop:
    def __init__(
        self,
        provider: LLMProvider,
        skills: SkillRegistry,
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_iterations: int = 6,
        sem_agent: asyncio.Semaphore | None = None,
        sem_llm: asyncio.Semaphore | None = None,
        user: Any = None,
        session_id: str = "",
        services: Any = None,
    ) -> None:
        self.provider = provider
        self.skills = skills
        self.model = model
        self.temperature = temperature
        self.max_iterations = max_iterations
        self.sem_agent = sem_agent
        self.sem_llm = sem_llm
        self.user = user
        self.session_id = session_id
        self.services = services

    async def run(
        self, history: list[Message], user_message: str
    ) -> AsyncIterator[StreamEvent]:
        """Run one user turn. Mutates `history` in place and yields observation events.
        The caller owns persistence."""
        if self.sem_agent is not None:
            await self.sem_agent.acquire()
        try:
            history.append(Message.text("user", user_message))
            system_msg = Message(
                role="system",
                blocks=[
                    TextBlock(
                        text=assemble_system_prompt(self.skills.system_prompt_fragments())
                    )
                ],
            )
            for _ in range(self.max_iterations):
                msgs = [system_msg, *history]
                text_parts: list[str] = []
                acc: dict[int, dict[str, Any]] = {}
                async for delta in self._stream(msgs):
                    if isinstance(delta, TextDelta):
                        text_parts.append(delta.text)
                        yield TokenEvent(text=delta.text)
                    elif isinstance(delta, ToolCallDelta):
                        slot = acc.setdefault(
                            delta.index, {"id": None, "name": None, "args": ""}
                        )
                        if delta.id:
                            slot["id"] = delta.id
                        if delta.name:
                            slot["name"] = delta.name
                        slot["args"] += delta.arguments_chunk
                    # Finish deltas need no action; the stream simply ends.

                calls = self._build_calls(acc)
                text = "".join(text_parts)

                if not calls:
                    blocks: list[Any] = [TextBlock(text=text)] if text else []
                    history.append(Message(role="assistant", blocks=blocks))
                    yield FinalEvent()
                    return

                tool_use_blocks = [
                    ToolUseBlock(id=c["id"], name=c["name"], arguments=c["args"]) for c in calls
                ]
                ablocks: list[Any] = ([TextBlock(text=text)] if text else []) + tool_use_blocks
                history.append(Message(role="assistant", blocks=ablocks))
                for c in calls:
                    yield ToolStartEvent(
                        tool_call_id=c["id"], name=c["name"], arguments=c["args"]
                    )

                events, stop = await self._dispatch_calls(calls, history)
                for ev in events:
                    yield ev
                if stop:
                    return

            yield ErrorEvent(
                code="max_iter", message=f"exceeded {self.max_iterations} iterations"
            )
        finally:
            if self.sem_agent is not None:
                self.sem_agent.release()

    async def _stream(self, msgs: list[Message]) -> AsyncIterator[LLMDelta]:
        if self.sem_llm is not None:
            await self.sem_llm.acquire()
        try:
            async for d in self.provider.stream(
                msgs,
                self.skills.all_tool_schemas(),
                model=self.model,
                temperature=self.temperature,
            ):
                yield d
        finally:
            if self.sem_llm is not None:
                self.sem_llm.release()

    def _build_calls(self, acc: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
        calls: list[dict[str, Any]] = []
        for idx in sorted(acc):
            slot = acc[idx]
            tid = slot["id"] or f"call_{idx}"
            name = slot["name"] or ""
            raw = slot["args"]
            try:
                args = parse_tool_arguments(raw) if raw else {}
                calls.append({"id": tid, "name": name, "args": args, "error": None})
            except ToolCallParseError:
                calls.append(
                    {
                        "id": tid,
                        "name": name,
                        "args": {"_raw": raw},
                        "error": "arguments were not valid JSON; please resend valid arguments",
                    }
                )
        return calls

    async def _dispatch_calls(
        self, calls: list[dict[str, Any]], history: list[Message]
    ) -> tuple[list[StreamEvent], bool]:
        """Run tool calls concurrently; return their events and whether the turn should end
        (a skill raised EndTurn). Parse-failed calls yield error results directly."""
        events: list[StreamEvent] = []
        errored = [c for c in calls if c["error"]]
        valid = [c for c in calls if not c["error"]]

        for c in errored:
            content = c["error"] or ""
            events.append(
                ToolResultEvent(
                    tool_call_id=c["id"], name=c["name"], is_error=True, content=content
                )
            )
            history.append(
                Message(
                    role="tool",
                    blocks=[
                        ToolResultBlock(tool_use_id=c["id"], content=content, is_error=True)
                    ],
                )
            )

        if valid:
            outcomes = await asyncio.gather(*[self._run_one(c) for c in valid])
            for c, (ctx, kind, payload) in zip(valid, outcomes, strict=True):
                events.extend(ctx.pending)
                if kind == "endturn":
                    events.append(FinalEvent())
                    return events, True
                is_error = kind == "error"
                events.append(
                    ToolResultEvent(
                        tool_call_id=c["id"],
                        name=c["name"],
                        is_error=is_error,
                        content=payload,
                        details=getattr(ctx, "details", None),
                    )
                )
                history.append(
                    Message(
                        role="tool",
                        blocks=[
                            ToolResultBlock(
                                tool_use_id=c["id"], content=payload, is_error=is_error
                            )
                        ],
                    )
                )
        return events, False

    async def _run_one(
        self, c: dict[str, Any]
    ) -> tuple[SkillContext, str, str]:
        ctx = SkillContext(
            user=self.user, session_id=self.session_id, services=self.services
        )
        try:
            result = await self.skills.dispatch(c["name"], ctx, **c["args"])
            return ctx, "ok", result
        except EndTurn:
            return ctx, "endturn", ""
        except Exception as e:  # noqa: BLE001 - surface as a tool error so the model can react
            return ctx, "error", f"tool '{c['name']}' failed: {e}"
