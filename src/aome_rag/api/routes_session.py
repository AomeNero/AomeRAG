"""Session management endpoints (scoped to the authenticated user)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from aome_rag.session.store import SessionNotFound

from .auth import User, get_current_user
from .deps import get_state
from .schemas import CreateSessionRequest, SessionOut

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
