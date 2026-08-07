"""健康检查：/health、/readyz、/stats。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from .deps import get_state

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """存活探针——进程在就跑 200。"""
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(state=Depends(get_state)) -> dict[str, str]:
    """就绪探针——报告依赖是否装配齐。"""
    settings = state.settings
    return {
        "db": "ok" if getattr(state, "session_store", None) is not None else "down",
        "zvec": "ok" if getattr(state, "store", None) is not None else "down",
        "retriever": "ok" if getattr(state, "retriever", None) is not None else "down",
        "provider": "ok" if getattr(state, "provider", None) is not None else "down",
        "deepseek_key": "present" if settings.deepseek_api_key else "missing",
    }


@router.get("/stats")
async def stats(state=Depends(get_state)) -> dict[str, object]:
    """给界面用的系统信息：知识库规模 + 模型/配置。"""
    settings = state.settings
    try:
        n_chunks: int = state.store.chunk_count()
    except Exception:  # noqa: BLE001 - store not ready / stats unavailable
        n_chunks = 0
    return {
        "n_chunks": n_chunks,
        "llm_model": settings.deepseek_model,
        "embed_model": settings.ollama_embed_model,
        "embed_dim": settings.embed_dim,
        "collection": settings.kb_collection,
        "top_k": settings.top_k,
    }
