"""Admin endpoints: file listing, vector reset, cross-user sessions + SPA route for /admin."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse

from .auth import User, get_current_user
from .deps import get_state

router = APIRouter(tags=["admin"])


@router.get("/admin/files")
async def list_files(
    type: str = Query("raw-data", pattern="^(raw-data|md-data)$"),
    user: User = Depends(get_current_user),
    state=Depends(get_state),
) -> dict:
    """List files in raw-data or md-data directory."""
    dir_path = state.settings.raw_data_dir if type == "raw-data" else state.settings.md_data_dir
    base = Path(dir_path)
    files: list[dict] = []
    if base.is_dir():
        for p in sorted(base.rglob("*")):
            if p.is_file():
                files.append({"name": p.relative_to(base).as_posix(), "size": p.stat().st_size})
    return {"dir": dir_path, "type": type, "n_files": len(files), "files": files}


@router.post("/admin/reset")
async def reset_store(
    user: User = Depends(get_current_user), state=Depends(get_state)
) -> dict:
    """Clear the vector store (danger zone — destroys all chunks, irreversible)."""
    state.store.clear()
    return {"ok": True, "message": "vector store cleared"}


@router.get("/admin/sessions")
async def list_all_sessions(
    user: User = Depends(get_current_user), state=Depends(get_state)
) -> list[dict]:
    """Admin: list sessions across ALL users (not scoped)."""
    return await state.session_store.list_all_sessions()


@router.get("/admin", response_model=None)
async def admin_spa(state=Depends(get_state)):
    """Serve index.html for /admin (React Router handles client-side routing)."""
    index = Path(state.settings.frontend_dist) / "index.html"
    if index.is_file():
        return FileResponse(str(index))
    return {"detail": "frontend not built — run `npm run build` in web/"}
