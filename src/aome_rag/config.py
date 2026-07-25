"""Application configuration, env-driven via pydantic-settings.

Env var names are the UPPER_CASED field names (no prefix), e.g. DEEPSEEK_API_KEY, ZVEC_PATH.
A `.env` file in the project root is loaded if present.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
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
    max_iterations: int = 6

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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings singleton for the running app."""
    return Settings()
