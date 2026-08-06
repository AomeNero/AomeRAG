"""Application configuration, env-driven via pydantic-settings.

Env var names are the UPPER_CASED field names (no prefix), e.g. DEEPSEEK_API_KEY, ZVEC_PATH.
A `.env` file in the project root is loaded if present.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root: two levels up from src/aome_rag/config.py → D:\Code\AomeCode
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- LLM (DeepSeek, OpenAI-compatible) ----
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"  # reasoner does NOT support tools — do not use
    max_concurrent_llm: int = 8

    # ---- Ollama (bge-m3 dense embeddings) ----
    ollama_base_url: str = "http://localhost:11434"
    ollama_embed_model: str = "bge-m3"
    embed_dim: int = 1024
    max_concurrent_embeds: int = 4

    # ---- Zvec (in-process vector DB) ----
    zvec_path: str = "./data/zvec"
    kb_collection: str = "kb_chunks_v1"

    # ---- Retrieval (dense + Zvec FTS hybrid) ----
    top_k: int = 6
    dense_weight: float = 0.7
    fts_weight: float = 0.3

    # ---- Agent loop ----
    max_concurrent_loops: int = 16
    max_iterations: int = 12

    # ---- Session history (SQLite) ----
    sqlite_path: str = "./data/sessions.db"

    # ---- Auth (v1: comma-separated tokens; X-User-Id trusted from a gateway) ----
    auth_tokens: str = ""

    # ---- Skills drop-in directory ----
    skills_dir: str = "./skills"

    # ---- Raw data (originals: PDF/docx/…) and cleaned markdown output ----
    raw_data_dir: str = "./raw/raw-data"
    md_data_dir: str = "./raw/md-data"

    # ---- Built frontend dist (served by FastAPI in prod when present; dev uses Vite) ----
    frontend_dist: str = "./web/dist"

    log_level: str = "INFO"

    # ---- File logging (logs/app/ + logs/access/, daily rotation) ----
    log_dir: str = "./logs"
    log_to_file: bool = True  # master switch; False → console only
    log_app_to_file: bool = True  # app + uvicorn lifecycle/error logs
    log_access_to_file: bool = True  # uvicorn per-request access logs
    log_retention_days: int = 30  # daily files kept, then auto-deleted

    # ---- Agent workspace (sandbox for the built-in read/write/edit/bash tools) ----
    workspace_dir: str = "./workspace"

    def model_post_init(self, __context: object) -> None:
        """Resolve relative paths against the project root so CWD doesn't matter."""
        for field in (
            "zvec_path", "sqlite_path", "skills_dir",
            "raw_data_dir", "md_data_dir", "frontend_dist", "log_dir", "workspace_dir",
        ):
            p = Path(getattr(self, field))
            if not p.is_absolute():
                setattr(self, field, str(_PROJECT_ROOT / p))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings singleton for the running app."""
    return Settings()
