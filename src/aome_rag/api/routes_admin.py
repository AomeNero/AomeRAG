"""管理端接口：文件列表、向量库重置、跨用户会话与反馈管理。"""

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
    """列出 raw-data 或 md-data 目录中的文件。"""
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
    """清空向量库（危险操作——销毁所有 chunk，不可恢复）。"""
    state.store.clear()
    await state.chunk_meta.clear()
    await state.clean_state.clear()
    return {"ok": True, "message": "vector store cleared"}


@router.get("/admin/sessions")
async def list_all_sessions(
    user: User = Depends(get_current_user), state=Depends(get_state)
) -> list[dict]:
    """管理端：列出所有用户的会话（不按用户限定）。"""
    return await state.session_store.list_all_sessions()


@router.get("/admin/sessions/{session_id}/messages")
async def admin_get_messages(
    session_id: str,
    user: User = Depends(get_current_user),
    state=Depends(get_state),
) -> list[dict]:
    """管理端：获取任意会话的消息（不按用户限定）。"""
    msgs = await state.session_store.get_messages_admin(session_id)
    return [{"role": m.role, "text": m.as_text()} for m in msgs]


@router.get("/admin", response_model=None)
async def admin_spa(state=Depends(get_state)):
    """为 /admin 提供 index.html（React Router 处理客户端路由）。"""
    index = Path(state.settings.frontend_dist) / "index.html"
    if index.is_file():
        return FileResponse(str(index))
    return {"detail": "frontend not built — run `npm run build` in web/"}


# ─── KB management (知识库管理) ──────────────────────────────────────────────
# 管理端知识库页由 chunk_meta 侧表驱动（zvec 无法枚举 chunk）。
# source_doc 经查询参数传入（可能含斜杠/中文）。


def _resolve_md(md_data_dir: str, source_doc: str) -> Path:
    """在 md_data_dir 内解析 source_doc 相对路径，阻止路径穿越。"""
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
    """分页的知识库文档列表 = md-data 文件与 chunk_meta 的 source_doc 取并集。"""
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
    """单个文档的 chunk 详情（来自侧表）。"""
    return {"source_doc": source_doc, "chunks": await state.chunk_meta.chunks_for_source(source_doc)}


@router.delete("/admin/kb/file")
async def kb_delete_file(
    source_doc: str,
    user: User = Depends(get_current_user),
    state=Depends(get_state),
) -> dict:
    """只删除 md-data 文件（向量库中的 chunk 不动）。"""
    target = _resolve_md(state.settings.md_data_dir, source_doc)
    os.remove(target)
    return {"ok": True, "source_doc": source_doc}


@router.delete("/admin/kb/doc-chunks")
async def kb_delete_doc_chunks(
    source_doc: str,
    user: User = Depends(get_current_user),
    state=Depends(get_state),
) -> dict:
    """删除某个文档的全部向量 chunk（zvec + 侧表）；md 文件保留。"""
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
    """删除单个 chunk（zvec + 侧表）。"""
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
    """重新入库单个 md-data 文档（向量化需要 Ollama 在线）。"""
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
    """从 md-data 文件重建 chunk_meta 侧表（不向量化）。"""
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
