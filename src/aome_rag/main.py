"""FastAPI application factory + lifespan wiring.

The lifespan opens Zvec, the SQLite session DB, builds the concurrency primitives
(semaphores / lock / executor), the provider, the skill registry, the retriever and the
ingestion pipeline, and hangs them on `app.state`. `create_app(overrides=...)` lets tests
inject fakes (FakeProvider, temp stores, ...); the lifespan only cleans up what it built."""

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
    ov: dict = app.state._overrides

    # --- always-built infra ---
    built_executor = "executor" not in ov
    app.state.zvec_executor = ov.get("executor") or ThreadPoolExecutor(max_workers=4)
    app.state.ingestion_lock = asyncio.Lock()
    app.state.sem_agent = asyncio.Semaphore(settings.max_concurrent_loops)
    app.state.sem_llm = asyncio.Semaphore(settings.max_concurrent_llm)
    app.state.sem_ollama = asyncio.Semaphore(settings.max_concurrent_embeds)

    # --- session store ---
    built_db = "session_db" not in ov
    app.state.session_db = ov.get("session_db") or await open_db(settings.sqlite_path)
    app.state.session_store = ov.get("session_store") or SessionStore(app.state.session_db)
    app.state.chunk_meta = ov.get("chunk_meta") or ChunkMetaStore(app.state.session_db)
    app.state.clean_state = ov.get("clean_state") or CleanStateStore(app.state.session_db)
    app.state.ingest_state = ov.get("ingest_state") or CleanStateStore(
        app.state.session_db, "ingest_state"
    )

    # --- retrieval ---
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

    # --- ingestion ---
    app.state.ingestion = ov.get("ingestion") or IngestionPipeline(
        Parser(), Chunker(), app.state.embedder, app.state.store,
        app.state.ingestion_lock, app.state.zvec_executor,
        chunk_meta=app.state.chunk_meta,
        ingest_state=app.state.ingest_state,
    )

    # --- cleaning (raw-data → md-data) ---
    app.state.cleaning = ov.get("cleaning") or CleaningPipeline(
        Converter(), app.state.zvec_executor, clean_state=app.state.clean_state
    )

    # --- provider ---
    app.state.provider = ov.get("provider") or OpenAICompatProvider(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        model=settings.deepseek_model,
    )

    # --- skills ---
    if "skills" in ov:
        app.state.skills = ov["skills"]
    else:
        registry = SkillRegistry()
        registry.register(KbSearchSkill())
        registry.register(ClarifySkill())
        registry.register(SkillLoaderSkill())
        registry.discover(settings.skills_dir)
        app.state.skills = registry

    yield

    # --- cleanup only what we built ---
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
    # Serve the built frontend last (API routes above take precedence). Only mounts when the
    # dist dir exists; in dev the Vite server serves the frontend and this is skipped.
    # Mount /images BEFORE the catch-all frontend `/` mount, or the root static mount
    # (which matches everything) would shadow it and /images/* would 404.
    _maybe_mount_images(app)
    _maybe_mount_frontend(app)
    return app


def _maybe_mount_images(app: FastAPI) -> None:
    """Serve md-data/images/ at /images/ so markdown ![](images/xxx.png) can load."""
    images_dir = Path(app.state.settings.md_data_dir) / "images"
    if images_dir.is_dir():
        app.mount("/images", StaticFiles(directory=str(images_dir)), name="kb-images")


def _maybe_mount_frontend(app: FastAPI) -> None:
    dist = Path(app.state.settings.frontend_dist)
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="frontend")


# Module-level app for `uvicorn aome_rag.main:app`.
app = create_app()
