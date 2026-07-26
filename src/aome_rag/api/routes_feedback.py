"""Feedback endpoints: submit rating / missing-info, admin list."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from .auth import User, get_current_user
from .deps import get_state

router = APIRouter(tags=["feedback"])


class FeedbackBody(BaseModel):
    type: str  # 'rating' | 'missing'
    session_id: str | None = None
    message_id: str | None = None
    rating: str | None = None  # 'up' | 'down'
    user_question: str | None = None
    ai_answer: str | None = None
    comment: str | None = None


@router.post("/feedback")
async def submit_feedback(
    body: FeedbackBody,
    user: User = Depends(get_current_user),
    state=Depends(get_state),
) -> dict:
    """Submit a feedback record (rating or missing-info)."""
    data = body.model_dump()
    data["user_id"] = user.id
    fid = await state.session_store.submit_feedback(data)
    return {"ok": True, "id": fid}


@router.get("/admin/feedback/all")
async def list_feedback(
    user: User = Depends(get_current_user), state=Depends(get_state)
) -> list[dict]:
    """Admin: list all feedback across users."""
    return await state.session_store.list_all_feedback()


@router.delete("/admin/feedback/{feedback_id}")
async def delete_feedback(
    feedback_id: str,
    user: User = Depends(get_current_user),
    state=Depends(get_state),
) -> dict:
    ok = await state.session_store.delete_feedback(feedback_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="feedback not found")
    return {"ok": True}
