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
from .api.routes_chat import router as chat_router
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
from .session.db import open_db
from .session.store import SessionStore
from .skills.clarify import ClarifySkill
from .skills.kb_search import KbSearchSkill
from .skills.registry import SkillRegistry


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    configure_logging(settings.log_level)
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
    )

    # --- cleaning (raw-data → md-data) ---
    app.state.cleaning = ov.get("cleaning") or CleaningPipeline(
        Converter(), app.state.zvec_executor
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
    app.include_router(health_router)
    app.include_router(chat_router)
    app.include_router(ingest_router)
    app.include_router(clean_router)
    app.include_router(session_router)
    # Serve the built frontend last (API routes above take precedence). Only mounts when the
    # dist dir exists; in dev the Vite server serves the frontend and this is skipped.
    _maybe_mount_frontend(app)
    return app


def _maybe_mount_frontend(app: FastAPI) -> None:
    dist = Path(app.state.settings.frontend_dist)
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="frontend")


# Module-level app for `uvicorn aome_rag.main:app`.
app = create_app()
