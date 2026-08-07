"""会话行模型。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SessionMeta:
    id: str
    title: str | None
    created_at: float
    updated_at: float
