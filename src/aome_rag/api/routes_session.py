"""会话管理接口（限定当前用户）：列表 / 消息 / 删除 / 标题。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from aome_rag.providers.messages import Message
from aome_rag.session.store import SessionNotFound

from .auth import User, get_current_user
from .deps import get_state
from .schemas import CreateSessionRequest, SessionOut, TitleBody

router = APIRouter(tags=["sessions"])


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(
    user: User = Depends(get_current_user), state=Depends(get_state)
) -> list[SessionOut]:
    metas = await state.session_store.list_sessions(user.id)
    return [SessionOut(**m.__dict__) for m in metas]


@router.post("/sessions", response_model=SessionOut)
async def create_session(
    body: CreateSessionRequest, user: User = Depends(get_current_user), state=Depends(get_state)
) -> SessionOut:
    sid = await state.session_store.create_session(user.id, title=body.title)
    metas = await state.session_store.list_sessions(user.id)
    meta = next((m for m in metas if m.id == sid), None)
    return SessionOut(**meta.__dict__)


@router.get("/sessions/search")
async def search_sessions(
    q: str = Query(..., min_length=1, description="search keyword"),
    user: User = Depends(get_current_user),
    state=Depends(get_state),
) -> list[dict]:
    """在用户的会话消息 + 标题里做关键词搜索。"""
    return await state.session_store.search_messages(user.id, q)


@router.get("/sessions/{session_id}/messages")
async def get_messages(
    session_id: str, user: User = Depends(get_current_user), state=Depends(get_state)
) -> list[dict]:
    msgs = await state.session_store.get_messages(session_id, user.id)
    return _messages_to_dicts(msgs)


def _messages_to_dicts(msgs: list[Message]) -> list[dict]:
    """转成 API 形态的消息。把 assistant 的 tool_use 块与紧随其后的 tool 消息
    tool_result 块配对，重建出 toolEvents。"""
    result: list[dict] = []
    # 建立 tool_use_id → ToolResultBlock 的查找表
    result_blocks: dict[str, Any] = {}
    for m in msgs:
        for b in m.tool_results():
            result_blocks[b.tool_use_id] = b

    for m in msgs:
        d: dict = {"role": m.role, "text": m.as_text()}
        tool_uses = m.tool_uses()
        if tool_uses:
            d["toolEvents"] = []
            for tu in tool_uses:
                tr = result_blocks.get(tu.id)
                d["toolEvents"].append({
                    "id": tu.id,
                    "name": tu.name,
                    "status": "error" if (tr and tr.is_error) else "ok",
                    "content": tr.content if tr else "",
                })
        result.append(d)
    return result


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str, user: User = Depends(get_current_user), state=Depends(get_state)
) -> dict:
    ok = await state.session_store.delete_session(session_id, user.id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")
    return {"ok": True}


@router.post("/sessions/{session_id}/title")
async def generate_title(
    session_id: str, user: User = Depends(get_current_user), state=Depends(get_state)
) -> dict:
    """让 LLM 把会话总结成简短（≤15 字）标题。"""
    msgs = await state.session_store.get_messages(session_id, user.id)
    if not msgs:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="empty session")
    transcript = "\n".join(f"{m.role}: {m.as_text()}" for m in msgs[:4])
    prompt = [
        Message.text(
            "system",
            "把下面的对话概括成一个简短的中文标题：不超过 15 个字、不要标点符号、"
            "不要「对话/问答/咨询」之类后缀、只输出标题本身。",
        ),
        Message.text("user", transcript),
    ]
    title = ""
    try:
        resp = await state.provider.complete(
            prompt, tools=[], model=state.settings.deepseek_model,
            temperature=0.3, max_tokens=30,
        )
        title = " ".join(resp.message.as_text().split()).strip("“”\"'")[:15]
    except Exception:  # noqa: BLE001 - fall back to heuristic if the LLM call fails
        title = ""
    if not title:
        first = msgs[0].as_text().splitlines()[0] if msgs[0].as_text() else ""
        title = (first[:15] or "新对话")
    await state.session_store.set_title(session_id, user.id, title)
    return {"title": title}


@router.patch("/sessions/{session_id}")
async def update_session_title(
    session_id: str,
    body: TitleBody,
    user: User = Depends(get_current_user),
    state=Depends(get_state),
) -> dict:
    """手动重命名会话。"""
    title = body.title.strip()[:50]
    ok = await state.session_store.set_title(session_id, user.id, title)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")
    return {"ok": True, "title": title}
