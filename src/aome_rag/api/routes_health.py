"""Health endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from .deps import get_state

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness — always 200 if the process is up."""
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(state=Depends(get_state)) -> dict[str, str]:
    """Readiness — reports whether wired dependencies are present."""
    settings = state.settings
    return {
        "db": "ok" if getattr(state, "session_store", None) is not None else "down",
        "zvec": "ok" if getattr(state, "store", None) is not None else "down",
        "retriever": "ok" if getattr(state, "retriever", None) is not None else "down",
        "provider": "ok" if getattr(state, "provider", None) is not None else "down",
        "deepseek_key": "present" if settings.deepseek_api_key else "missing",
    }
