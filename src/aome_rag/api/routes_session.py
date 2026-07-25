"""Session management endpoints (scoped to the authenticated user)."""

from __future__ import annotations

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
    """Keyword-search across the user's session messages + titles."""
    return await state.session_store.search_messages(user.id, q)


@router.get("/sessions/{session_id}/messages")
async def get_messages(
    session_id: str, user: User = Depends(get_current_user), state=Depends(get_state)
) -> list[dict]:
    msgs = await state.session_store.get_messages(session_id, user.id)
    return [{"role": m.role, "text": m.as_text()} for m in msgs]


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
    """Ask the LLM to summarize the session into a short (≤15 char) title."""
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
    """Manually rename a session."""
    title = body.title.strip()[:50]
    ok = await state.session_store.set_title(session_id, user.id, title)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")
    return {"ok": True, "title": title}
