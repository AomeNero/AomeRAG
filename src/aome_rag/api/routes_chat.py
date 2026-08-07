"""POST /chat —— SSE 流式（默认）或 JSON。跑一轮 agent，把新消息持久化到会话。"""

from __future__ import annotations

import structlog

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from aome_rag.agent.events import (
    ClarifyEvent,
    ErrorEvent,
    TokenEvent,
    ToolResultEvent,
    ToolStartEvent,
)

_log = structlog.get_logger()
from aome_rag.agent.loop import AgentLoop
from aome_rag.providers.messages import Message
from aome_rag.services import Services

from .auth import User, get_current_user
from .deps import get_state
from .schemas import ChatRequest
from .sse import sse_event

router = APIRouter(tags=["chat"])


async def _persist(state, sid: str, user: User, new_msgs: list[Message]) -> None:
    for m in new_msgs:
        try:
            await state.session_store.append_message(sid, user.id, m)
        except Exception:  # noqa: BLE001 - persistence must not break the stream
            pass


@router.post("/chat")
async def chat(
    req: ChatRequest,
    user: User = Depends(get_current_user),
    state=Depends(get_state),
):
    sid = req.session_id or await state.session_store.create_session(user.id)
    history = await state.session_store.get_messages(sid, user.id)
    _log.info("chat.request", session_id=sid, stream=req.stream, user=user.id)
    services = Services(
        retriever=state.retriever,
        session_store=state.session_store,
        ingestion=state.ingestion,
    )
    loop = AgentLoop(
        state.provider,
        state.skills,
        model=state.settings.deepseek_model,
        max_iterations=state.settings.max_iterations,
        sem_agent=state.sem_agent,
        sem_llm=state.sem_llm,
        user=user,
        session_id=sid,
        services=services,
    )
    orig = len(history)

    if req.stream:
        async def gen():
            yield sse_event({"type": "session", "session_id": sid})
            try:
                async for ev in loop.run(history, req.message):
                    yield sse_event(ev.model_dump())
                _log.info("chat.stream.done", session_id=sid)
            finally:
                await _persist(state, sid, user, history[orig:])

        return StreamingResponse(
            gen(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # 非流式模式
    answer: list[str] = []
    tool_events: list[dict] = []
    clarify: str | None = None
    error: dict | None = None
    try:
        async for ev in loop.run(history, req.message):
            if isinstance(ev, TokenEvent):
                answer.append(ev.text)
            elif isinstance(ev, ClarifyEvent):
                clarify = ev.question
            elif isinstance(ev, ErrorEvent):
                error = ev.model_dump()
            elif isinstance(ev, (ToolStartEvent, ToolResultEvent)):
                tool_events.append(ev.model_dump())
    finally:
        await _persist(state, sid, user, history[orig:])

    _log.info(
        "chat.answer.done", session_id=sid,
        answer_len=len(answer), error=bool(error), n_tool_events=len(tool_events),
    )
    return {
        "session_id": sid,
        "answer": "".join(answer),
        "clarify": clarify,
        "error": error,
        "tool_events": tool_events,
    }
