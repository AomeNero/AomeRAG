"""HTTP request/response shapes."""

from __future__ import annotations

from pydantic import BaseModel


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str
    stream: bool = True


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    clarify: str | None = None
    error: dict | None = None
    tool_events: list[dict] = []


class IngestResponse(BaseModel):
    n_docs: int
    n_chunks: int
    n_failed: int
    errors: list[str]
    elapsed_s: float


class SessionOut(BaseModel):
    id: str
    title: str | None
    created_at: float
    updated_at: float


class CreateSessionRequest(BaseModel):
    title: str | None = None
