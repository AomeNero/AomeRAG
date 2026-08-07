"""应用配置：pydantic-settings 从环境变量读取，支持 .env 文件；相对路径统一以项目根为基准解析。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录：src/aome_rag/config.py 上两级
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- LLM（DeepSeek，OpenAI 兼容）----
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"  # reasoner does NOT support tools — do not use
    max_concurrent_llm: int = 8

    # ---- Ollama（bge-m3 dense 向量嵌入）----
    ollama_base_url: str = "http://localhost:11434"
    ollama_embed_model: str = "bge-m3"
    embed_dim: int = 1024
    max_concurrent_embeds: int = 4

    # ---- Zvec（进程内向量库）----
    zvec_path: str = "./data/zvec"
    kb_collection: str = "kb_chunks_v1"

    # ---- 检索（dense + Zvec FTS 混合）----
    top_k: int = 6
    dense_weight: float = 0.7
    fts_weight: float = 0.3

    # ---- Agent 循环 ----
    max_concurrent_loops: int = 16
    max_iterations: int = 12

    # ---- 会话历史（SQLite）----
    sqlite_path: str = "./data/sessions.db"

    # ---- 鉴权（v1：逗号分隔 token；信任网关传来的 X-User-Id）----
    auth_tokens: str = ""

    # ---- 技能即插目录 ----
    skills_dir: str = "./skills"

    # ---- 原始数据（PDF/docx/…）与清洗后的 markdown 输出 ----
    raw_data_dir: str = "./raw/raw-data"
    md_data_dir: str = "./raw/md-data"

    # ---- 前端构建产物（存在时由 FastAPI 托管；开发用 Vite）----
    frontend_dist: str = "./web/dist"

    log_level: str = "INFO"

    # ---- 文件日志（logs/app/ + logs/access/，按天轮转）----
    log_dir: str = "./logs"
    log_to_file: bool = True  # master switch; False → console only
    log_app_to_file: bool = True  # app + uvicorn lifecycle/error logs
    log_access_to_file: bool = True  # uvicorn per-request access logs
    log_retention_days: int = 30  # daily files kept, then auto-deleted

    # ---- Agent 工作区（内置 read/write/edit/bash 工具的沙箱）----
    workspace_dir: str = "./workspace"
    workspace_retention_days: int = 7  # 启动时清理 N 天前的生成文件

    def model_post_init(self, __context: object) -> None:
        """把相对路径解析为基于项目根，避免受当前工作目录影响。"""
        for field in (
            "zvec_path", "sqlite_path", "skills_dir",
            "raw_data_dir", "md_data_dir", "frontend_dist", "log_dir", "workspace_dir",
        ):
            p = Path(getattr(self, field))
            if not p.is_absolute():
                setattr(self, field, str(_PROJECT_ROOT / p))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """运行中应用的缓存配置单例。"""
    return Settings()
