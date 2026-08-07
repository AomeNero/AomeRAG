"""POST /clean/dir 与 /update/dir —— 清洗 raw-data → md-data（SSE 进度）。"""

from __future__ import annotations

import asyncio
from pathlib import Path

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
    """递归清洗 raw-data → md-data。SSE：scan → 每文件 start/done/skipped → summary。"""
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


@router.post("/update/dir")
async def update_dir(
    user: User = Depends(get_current_user), state=Depends(get_state)
):
    """增量更新：只清洗新增/变更的 raw 文件 → md，仅重新入库这些变更文档，
    并为已删除的文档移除 chunk。SSE：先清洗事件再入库事件。"""
    raw_dir = state.settings.raw_data_dir
    md_dir = state.settings.md_data_dir

    async def gen():
        changed_raw: list[str] = []
        deleted_raw: list[str] = []
        async for ev in state.cleaning.incremental_update(raw_dir, md_dir):
            t = ev.get("type")
            if t == "file_done" and ev.get("status") == "ok":
                changed_raw.append(ev["source_doc"])
            elif t == "deleted":
                deleted_raw.append(ev["source_doc"])
            yield sse_event(ev)

        # 只重新入库变更的文档（按 source_doc 先删后插）
        changed_md = [Path(r).with_suffix(".md").as_posix() for r in changed_raw]
        if changed_md:
            files = [(doc, str(Path(md_dir) / doc)) for doc in changed_md]
            async for ev in state.ingestion.ingest_files(files):
                yield sse_event(ev)

        # 为已删除的文档移除向量块
        if deleted_raw:
            loop = asyncio.get_running_loop()
            for r in deleted_raw:
                doc = Path(r).with_suffix(".md").as_posix()
                await loop.run_in_executor(state.zvec_executor, state.store.delete_by_source, doc)
                await state.chunk_meta.delete_source(doc)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/clean/dir/inc")
async def clean_dir_inc(
    user: User = Depends(get_current_user), state=Depends(get_state)
):
    """Incremental clean (清洗数据): only convert NEW/MODIFIED raw files → md and drop md for
    REMOVED files. Does NOT re-slice — run /ingest/dir/inc (矢量化数据) separately. Updates
    clean_state. SSE."""
    raw_dir = state.settings.raw_data_dir
    md_dir = state.settings.md_data_dir

    async def gen():
        async for ev in state.cleaning.incremental_update(raw_dir, md_dir):
            yield sse_event(ev)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
