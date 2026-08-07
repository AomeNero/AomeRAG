"""共享服务包：通过 SkillContext.services 注入给技能（retriever / session_store / ingestion）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Services:
    retriever: Any = None  # Phase 4: retrieval.Retriever
    session_store: Any = None  # Phase 6: session.store.SessionStore
    ingestion: Any = None  # Phase 5: ingestion.pipeline.IngestionPipeline
