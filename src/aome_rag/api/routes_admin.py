"""Admin endpoints: file listing, vector reset, cross-user sessions, KB management + SPA."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
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
    await state.chunk_meta.clear()
    await state.clean_state.clear()
    return {"ok": True, "message": "vector store cleared"}


@router.get("/admin/sessions")
async def list_all_sessions(
    user: User = Depends(get_current_user), state=Depends(get_state)
) -> list[dict]:
    """Admin: list sessions across ALL users (not scoped)."""
    return await state.session_store.list_all_sessions()


@router.get("/admin/sessions/{session_id}/messages")
async def admin_get_messages(
    session_id: str,
    user: User = Depends(get_current_user),
    state=Depends(get_state),
) -> list[dict]:
    """Admin: get messages for any session (no user scoping)."""
    msgs = await state.session_store.get_messages_admin(session_id)
    return [{"role": m.role, "text": m.as_text()} for m in msgs]


@router.get("/admin", response_model=None)
async def admin_spa(state=Depends(get_state)):
    """Serve index.html for /admin (React Router handles client-side routing)."""
    index = Path(state.settings.frontend_dist) / "index.html"
    if index.is_file():
        return FileResponse(str(index))
    return {"detail": "frontend not built — run `npm run build` in web/"}


# ─── KB management (知识库管理) ──────────────────────────────────────────────
# The admin KB page is driven by the chunk_meta side table (zvec can't enumerate
# chunks). source_doc is passed via query param (may contain slashes/CJK).


def _resolve_md(md_data_dir: str, source_doc: str) -> Path:
    """Resolve a source_doc relative path inside md_data_dir, blocking traversal."""
    base = Path(md_data_dir).resolve()
    target = (base / source_doc).resolve()
    if target != base and base not in target.parents:
        raise HTTPException(status_code=400, detail="invalid path")
    if not target.is_file() or target.suffix.lower() != ".md":
        raise HTTPException(status_code=404, detail="file not found")
    return target


@router.get("/admin/kb/docs")
async def kb_docs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    q: str = Query(""),
    filter: str = Query("", alias="filter"),
    user: User = Depends(get_current_user),
    state=Depends(get_state),
) -> dict:
    """Paginated KB document list = union of md-data files and chunk_meta source_docs."""
    md_dir = Path(state.settings.md_data_dir)
    files: set[str] = set()
    if md_dir.is_dir():
        for p in md_dir.rglob("*"):
            rel = p.relative_to(md_dir).as_posix()
            if rel.startswith("images/") or rel == "images":
                continue
            if p.is_file() and p.suffix.lower() == ".md":
                files.add(rel)
    counts = await state.chunk_meta.source_counts()
    items = []
    for doc in sorted(set(files) | set(counts)):
        n = counts.get(doc, 0)
        fe = doc in files
        status = "ok" if (fe and n > 0) else ("orphan" if (n > 0 and not fe) else "unsliced")
        if q and q.lower() not in doc.lower():
            continue
        if filter == "orphan" and status != "orphan":
            continue
        if filter == "unsliced" and status != "unsliced":
            continue
        if filter == "anomaly" and status == "ok":
            continue
        items.append({"source_doc": doc, "file_exists": fe, "n_chunks": n, "status": status})
    total = len(items)
    start = (page - 1) * page_size
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items[start : start + page_size],
    }


@router.get("/admin/kb/chunks")
async def kb_chunks(
    source_doc: str,
    user: User = Depends(get_current_user),
    state=Depends(get_state),
) -> dict:
    """Chunk detail for one document (from the side table)."""
    return {"source_doc": source_doc, "chunks": await state.chunk_meta.chunks_for_source(source_doc)}


@router.delete("/admin/kb/file")
async def kb_delete_file(
    source_doc: str,
    user: User = Depends(get_current_user),
    state=Depends(get_state),
) -> dict:
    """Delete an md-data file only (chunks in the vector store are untouched)."""
    target = _resolve_md(state.settings.md_data_dir, source_doc)
    os.remove(target)
    return {"ok": True, "source_doc": source_doc}


@router.delete("/admin/kb/doc-chunks")
async def kb_delete_doc_chunks(
    source_doc: str,
    user: User = Depends(get_current_user),
    state=Depends(get_state),
) -> dict:
    """Delete all vector chunks of one document (zvec + side table); the md file stays."""
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(state.zvec_executor, state.store.delete_by_source, source_doc)
    await state.chunk_meta.delete_source(source_doc)
    return {"ok": True, "source_doc": source_doc, "n_chunks": 0}


@router.delete("/admin/kb/chunk")
async def kb_delete_chunk(
    id: str,
    user: User = Depends(get_current_user),
    state=Depends(get_state),
) -> dict:
    """Delete a single chunk (zvec + side table)."""
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(state.zvec_executor, state.store.delete_chunk, id)
    await state.chunk_meta.delete_chunk(id)
    return {"ok": True, "chunk_id": id}


@router.post("/admin/kb/reingest")
async def kb_reingest(
    source_doc: str,
    user: User = Depends(get_current_user),
    state=Depends(get_state),
) -> dict:
    """Re-ingest a single md-data document (needs Ollama online for embedding)."""
    _resolve_md(state.settings.md_data_dir, source_doc)
    report = await state.ingestion.reingest_one(source_doc, state.settings.md_data_dir)
    if report.n_failed:
        raise HTTPException(status_code=500, detail="; ".join(report.errors))
    return {"ok": True, "source_doc": source_doc, "n_chunks": report.n_chunks}


@router.post("/admin/kb/sync")
async def kb_sync(
    user: User = Depends(get_current_user),
    state=Depends(get_state),
) -> dict:
    """Rebuild the chunk_meta side table from md-data files (no embedding)."""
    counts = await state.ingestion.sync_meta(state.settings.md_data_dir)
    return {"ok": True, **counts}


@router.post("/admin/kb/clean-state/clear")
async def kb_clear_clean_state(
    user: User = Depends(get_current_user),
    state=Depends(get_state),
) -> dict:
    """清空清洗记录 — the next 清洗数据 will then process everything (full clean)."""
    await state.clean_state.clear()
    return {"ok": True, "message": "clean_state cleared"}


@router.post("/admin/kb/ingest-state/clear")
async def kb_clear_ingest_state(
    user: User = Depends(get_current_user),
    state=Depends(get_state),
) -> dict:
    """清空切片记录 — the next 矢量化数据 will then re-slice everything (full ingest)."""
    await state.ingest_state.clear()
    return {"ok": True, "message": "ingest_state cleared"}
