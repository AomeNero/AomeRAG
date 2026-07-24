"""Shared service bag injected into skills via SkillContext.services.

Keeps skills decoupled from concrete implementations (the loop/app wire the real ones;
tests inject fakes). Grows phase by phase.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Services:
    retriever: Any = None  # Phase 4: retrieval.Retriever
    session_store: Any = None  # Phase 6: session.store.SessionStore
    ingestion: Any = None  # Phase 5: ingestion.pipeline.IngestionPipeline
