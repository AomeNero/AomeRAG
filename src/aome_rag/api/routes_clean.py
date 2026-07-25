"""POST /clean/dir — extract+clean raw-data → md-data (SSE progress)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from .auth import User, get_current_user
from .deps import get_state
from .sse import sse_event

router = APIRouter(tags=["clean"])


@router.post("/clean/dir")
async def clean_dir(
    user: User = Depends(get_current_user), state=Depends(get_state)
):
    """Recursively clean raw-data → md-data. SSE: scan → per-file start/done/skipped → summary."""
    raw_dir = state.settings.raw_data_dir
    md_dir = state.settings.md_data_dir

    async def gen():
        async for ev in state.cleaning.clean_dir(raw_dir, md_dir):
            yield sse_event(ev)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
