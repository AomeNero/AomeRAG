"""FastAPI 应用工厂 + lifespan 装配：启动时初始化 Zvec/SQLite/检索/摄入/清洗/Provider/技能注册表并挂到 app.state。"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .agent.loop import AgentLoop  # noqa: F401 - re-exported for convenience
from .api.routes_admin import router as admin_router
from .api.routes_chat import router as chat_router
from .api.routes_feedback import router as feedback_router
from .api.routes_health import router as health_router
from .api.routes_ingest import router as ingest_router
from .api.routes_clean import router as clean_router
from .api.routes_session import router as session_router
from .cleaning.cleaner import Converter
from .cleaning.pipeline import CleaningPipeline
from .config import Settings, get_settings
from .ingestion.parser import Parser
from .ingestion.chunker import Chunker
from .ingestion.pipeline import IngestionPipeline
from .logging import configure_logging
from .providers.openai_compat import OpenAICompatProvider
from .retrieval.embedder import OllamaEmbedder
from .retrieval.retriever import Retriever
from .retrieval.store import ZvecStore
from .services import Services  # noqa: F401
from .session.chunk_meta import ChunkMetaStore
from .session.clean_state import CleanStateStore
from .session.db import open_db
from .session.store import SessionStore
from .tools.clarify import ClarifySkill
from .tools.kb_search import KbSearchSkill
from .tools.registry import SkillRegistry
from .tools.skill_loader import SkillLoaderSkill
from .tools.workspace import BashTool, EditTool, ReadTool, WriteTool, cleanup_workspace


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    configure_logging(
        settings.log_level,
        log_dir=settings.log_dir,
        log_to_file=settings.log_to_file,
        log_app_to_file=settings.log_app_to_file,
        log_access_to_file=settings.log_access_to_file,
        retention_days=settings.log_retention_days,
    )
    # 清理 workspace 中超过保留期的生成文件（客户下载交付后自动回收）
    await asyncio.to_thread(
        cleanup_workspace, settings.workspace_dir, settings.workspace_retention_days
    )
    ov: dict = app.state._overrides

    # --- 总是构建的基础设施 ---
    built_executor = "executor" not in ov
    app.state.zvec_executor = ov.get("executor") or ThreadPoolExecutor(max_workers=4)
    app.state.ingestion_lock = asyncio.Lock()
    app.state.sem_agent = asyncio.Semaphore(settings.max_concurrent_loops)
    app.state.sem_llm = asyncio.Semaphore(settings.max_concurrent_llm)
    app.state.sem_ollama = asyncio.Semaphore(settings.max_concurrent_embeds)

    # --- 会话存储 ---
    built_db = "session_db" not in ov
    app.state.session_db = ov.get("session_db") or await open_db(settings.sqlite_path)
    app.state.session_store = ov.get("session_store") or SessionStore(app.state.session_db)
    app.state.chunk_meta = ov.get("chunk_meta") or ChunkMetaStore(app.state.session_db)
    app.state.clean_state = ov.get("clean_state") or CleanStateStore(app.state.session_db)
    app.state.ingest_state = ov.get("ingest_state") or CleanStateStore(
        app.state.session_db, "ingest_state"
    )

    # --- 检索 ---
    built_embedder = "embedder" not in ov
    app.state.store = ov.get("store") or ZvecStore(
        settings.zvec_path, settings.embed_dim, settings.kb_collection
    )
    app.state.embedder = ov.get("embedder") or OllamaEmbedder(
        settings.ollama_base_url, settings.ollama_embed_model, sem=app.state.sem_ollama
    )
    app.state.retriever = ov.get("retriever") or Retriever(
        app.state.store, app.state.embedder, app.state.zvec_executor, top_k=settings.top_k
    )

    # --- 入库 ---
    app.state.ingestion = ov.get("ingestion") or IngestionPipeline(
        Parser(), Chunker(), app.state.embedder, app.state.store,
        app.state.ingestion_lock, app.state.zvec_executor,
        chunk_meta=app.state.chunk_meta,
        ingest_state=app.state.ingest_state,
    )

    # --- 清洗（raw-data → md-data）---
    app.state.cleaning = ov.get("cleaning") or CleaningPipeline(
        Converter(), app.state.zvec_executor, clean_state=app.state.clean_state
    )

    # --- Provider ---
    app.state.provider = ov.get("provider") or OpenAICompatProvider(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        model=settings.deepseek_model,
    )

    # --- 技能 ---
    if "skills" in ov:
        app.state.skills = ov["skills"]
    else:
        registry = SkillRegistry()
        registry.register(KbSearchSkill())
        registry.register(ClarifySkill())
        registry.register(SkillLoaderSkill())
        registry.register(ReadTool(settings.workspace_dir))
        registry.register(WriteTool(settings.workspace_dir))
        registry.register(EditTool(settings.workspace_dir))
        registry.register(BashTool(settings.workspace_dir))
        registry.discover(settings.skills_dir)
        app.state.skills = registry

    yield

    # --- 只清理我们自己构建的东西 ---
    if built_executor:
        app.state.zvec_executor.shutdown(wait=False)
    if built_embedder:
        await app.state.embedder.aclose()
    if built_db:
        await app.state.session_db.close()


def create_app(settings: Settings | None = None, *, overrides: dict | None = None) -> FastAPI:
    app = FastAPI(title="AomeRAG", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings or get_settings()
    app.state._overrides = overrides or {}

    @app.middleware("http")
    async def _html_no_cache(request, call_next):
        # HTML 入口（index.html / /admin）不缓存：重建前端后资源 hash 会变，若浏览器
        # 缓存了旧 index.html 会引用旧资源名 → 404 → 白屏/无样式。API 是 JSON，不受影响。
        response = await call_next(request)
        if response.headers.get("content-type", "").startswith("text/html"):
            response.headers["Cache-Control"] = "no-cache"
        return response

    app.include_router(health_router)
    app.include_router(chat_router)
    app.include_router(ingest_router)
    app.include_router(clean_router)
    app.include_router(session_router)
    app.include_router(admin_router)
    app.include_router(feedback_router)
    # 最后托管前端（上面已注册的 API 路由优先）。仅当 dist 目录存在时才挂载；
    # 开发时由 Vite 服务前端，跳过此步。
    # /images 必须在兜底前端 `/` 挂载之前挂载，否则根静态挂载（匹配一切）
    # 会遮蔽它，导致 /images/* 404。
    _maybe_mount_images(app)
    _maybe_mount_workspace(app)
    _maybe_mount_frontend(app)
    return app


def _maybe_mount_workspace(app: FastAPI) -> None:
    """在 /workspace/ 托管 agent 工作区，让生成的文件可下载。
    在兜底前端挂载之前挂载；目录按需创建。"""
    ws = Path(app.state.settings.workspace_dir)
    ws.mkdir(parents=True, exist_ok=True)
    app.mount("/workspace", StaticFiles(directory=str(ws)), name="workspace")


def _maybe_mount_images(app: FastAPI) -> None:
    """在 /images/ 托管 md-data/images/，让 markdown ![](images/xxx.png) 能加载。"""
    images_dir = Path(app.state.settings.md_data_dir) / "images"
    if images_dir.is_dir():
        app.mount("/images", StaticFiles(directory=str(images_dir)), name="kb-images")


def _maybe_mount_frontend(app: FastAPI) -> None:
    dist = Path(app.state.settings.frontend_dist)
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="frontend")


# 模块级 app，供 `uvicorn aome_rag.main:app` 使用。
app = create_app()
