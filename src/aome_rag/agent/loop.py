"""Agent 循环：驱动 Provider 流式输出、累积工具调用、派发技能、维护对话记录、产出观察事件。"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import structlog

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
from ..tools.base import EndTurn, SkillContext
from ..tools.registry import SkillRegistry

_log = structlog.get_logger()


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
        """运行一轮用户对话。原地修改 `history` 并产出观察事件。
        持久化由调用方负责。"""
        if self.sem_agent is not None:
            await self.sem_agent.acquire()
        try:
            _log.info(
                "agent.turn",
                session_id=self.session_id, model=self.model, max_iterations=self.max_iterations,
            )
            history.append(Message.text("user", user_message))
            system_msg = Message(
                role="system",
                blocks=[
                    TextBlock(
                        text=assemble_system_prompt(self.skills.system_prompt_fragments())
                    )
                ],
            )
            for it in range(self.max_iterations):
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
                    # Finish delta 无需处理；流式正常结束。

                calls = self._build_calls(acc)
                text = "".join(text_parts)

                if not calls:
                    _log.info("agent.turn.done", session_id=self.session_id, n_iterations=it + 1)
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

            _log.warning(
                "agent.turn.max_iter", session_id=self.session_id,
                n_iterations=self.max_iterations,
            )
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
        """并发运行工具调用；返回它们的事件以及本轮是否应结束
        （某个技能抛了 EndTurn）。解析失败的调用直接产出错误结果。

        当任一技能抛 EndTurn（如 clarify）时立即返回，而不是等待
        较慢的并发任务（如 kb_search）结束。"""
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
            _log.info(
                "agent.tools.dispatch", session_id=self.session_id,
                n_valid=len(valid), n_errored=len(errored),
                tools=[c["name"] for c in valid],
            )

            async def _wrap(c: dict[str, Any]):
                return c, await self._run_one(c)

            task_to_call: dict[asyncio.Task, dict[str, Any]] = {}
            tasks: set[asyncio.Task] = set()
            for c in valid:
                t = asyncio.create_task(_wrap(c))
                task_to_call[t] = c
                tasks.add(t)
            while tasks:
                done, tasks = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                for t in done:
                    c, (ctx, kind, payload) = t.result()
                    events.extend(ctx.pending)
                    if kind == "endturn":
                        # 把澄清问题写回 assistant 消息，使其能持久化
                        # （ClarifyEvent 是临时/仅 SSE 的，不落库会丢）。
                        assistant_msg = history[-1]
                        if c["name"] == "clarify":
                            q = c.get("args", {}).get("question", "")
                            if q:
                                assistant_msg.blocks.insert(0, TextBlock(text=q))
                        # 为澄清工具加 ToolResultBlock 以便持久化
                        assistant_msg.blocks.append(
                            ToolResultBlock(tool_use_id=c["id"], content="", is_error=False)
                        )
                        # 标记澄清工具已完成，让前端关闭其转圈
                        events.append(
                            ToolResultEvent(
                                tool_call_id=c["id"],
                                name=c["name"],
                                is_error=False,
                                content="",
                            )
                        )
                        # 取消剩余任务并标记，让前端关闭对应转圈
                        for remaining in tasks:
                            remaining.cancel()
                            rc = task_to_call[remaining]
                            # 持久化被取消的工具结果，刷新后仍在
                            assistant_msg.blocks.append(
                                ToolResultBlock(tool_use_id=rc["id"], content="", is_error=False)
                            )
                            events.append(
                                ToolResultEvent(
                                    tool_call_id=rc["id"],
                                    name=rc["name"],
                                    is_error=False,
                                    content="",
                                    cancelled=True,
                                )
                            )
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
            _log.info(
                "agent.tool.result", session_id=self.session_id,
                tool=c["name"], kind="ok", result_len=len(result or ""),
            )
            return ctx, "ok", result
        except EndTurn:
            _log.info(
                "agent.tool.result", session_id=self.session_id,
                tool=c["name"], kind="endturn",
            )
            return ctx, "endturn", ""
        except Exception as e:  # noqa: BLE001 - surface as a tool error so the model can react
            _log.warning(
                "agent.tool.result", session_id=self.session_id,
                tool=c["name"], kind="error", error=str(e),
            )
            return ctx, "error", f"tool '{c['name']}' failed: {e}"
