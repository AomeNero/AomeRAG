"""POST /ingest（上传）与 /ingest/dir（目录扫描入库，SSE）。"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import StreamingResponse

from aome_rag.ingestion.parser import SUPPORTED_EXTS
from aome_rag.ingestion.pipeline import UploadedDoc

from .auth import User, get_current_user
from .deps import get_state
from .schemas import IngestResponse
from .sse import sse_event

router = APIRouter(tags=["ingest"])


@router.post("/ingest", response_model=IngestResponse)
async def ingest(
    files: list[UploadFile] = File(...),
    department: str | None = Form(None),
    user: User = Depends(get_current_user),
    state=Depends(get_state),
) -> IngestResponse:
    docs = [
        UploadedDoc(f.filename or f"doc_{i}.bin", await f.read()) for i, f in enumerate(files)
    ]
    report = await state.ingestion.ingest(docs, department=department)
    return IngestResponse(
        n_docs=report.n_docs,
        n_chunks=report.n_chunks,
        n_failed=report.n_failed,
        errors=report.errors,
        elapsed_s=report.elapsed_s,
    )


@router.post("/ingest/dir")
async def ingest_dir(
    department: str | None = Query(None),
    user: User = Depends(get_current_user),
    state=Depends(get_state),
):
    """递归入库配置的 RAW_DIR。SSE：scan -> 每文件 start/done/skipped -> summary。
    .md 直读；其它支持的类型走 markitdown。"""
    raw_dir = state.settings.md_data_dir
    base = Path(raw_dir)
    files: list[tuple[str, str]] = []  # (source_doc relative path, absolute path)
    skipped: list[str] = []
    if base.is_dir():
        for p in sorted(base.rglob("*")):
            rel = p.relative_to(base).as_posix()
            if rel.startswith("images/") or rel == "images":
                continue  # skip the images/ directory entirely (extracted PNGs, not docs)
            if p.is_dir():
                continue
            if p.suffix.lower() in SUPPORTED_EXTS:
                files.append((rel, str(p)))
            else:
                skipped.append(rel)

    async def gen():
        yield sse_event(
            {
                "type": "scan",
                "raw_dir": raw_dir,
                "n_files": len(files),
                "n_skipped": len(skipped),
            }
        )
        for s in skipped:
            yield sse_event(
                {"type": "skipped", "source_doc": s, "reason": "unsupported extension"}
            )
        async for ev in state.ingestion.ingest_files(files, department=department):
            yield sse_event(ev)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/ingest/dir/inc")
async def ingest_dir_inc(
    user: User = Depends(get_current_user),
    state=Depends(get_state),
):
    """增量入库：只重新切片新增/变更的 md 文件（内容哈希对比 ingest_state），
    为已删除文档移除 chunk。SSE。需要 Ollama 在线（向量化）。"""
    md_dir = state.settings.md_data_dir

    async def gen():
        async for ev in state.ingestion.incremental_ingest(md_dir):
            yield sse_event(ev)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
