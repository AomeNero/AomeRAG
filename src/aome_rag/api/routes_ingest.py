"""POST /ingest (multipart upload) and POST /ingest/dir (ingest a configured directory, SSE)."""

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
    """Recursively ingest the configured RAW_DIR. SSE: scan -> per-file start/done/skipped
    -> summary. .md is read directly; other supported types go through markitdown."""
    raw_dir = state.settings.raw_dir
    base = Path(raw_dir)
    files: list[tuple[str, str]] = []  # (source_doc relative path, absolute path)
    skipped: list[str] = []
    if base.is_dir():
        for p in sorted(base.rglob("*")):
            if p.is_dir():
                continue
            rel = p.relative_to(base).as_posix()
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
