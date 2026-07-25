"""Observation stream events yielded by the agent loop (serialized to SSE by the API layer)."""

from __future__ import annotations

from typing import Any, Literal, Union

from pydantic import BaseModel


class TokenEvent(BaseModel):
    type: Literal["token"] = "token"
    text: str


class ToolStartEvent(BaseModel):
    type: Literal["tool_start"] = "tool_start"
    tool_call_id: str
    name: str
    arguments: dict[str, Any]


class ToolResultEvent(BaseModel):
    type: Literal["tool_result"] = "tool_result"
    tool_call_id: str
    name: str
    is_error: bool
    content: str
    details: list[dict[str, Any]] | None = None  # structured hits for the UI (kb_search)


class ClarifyEvent(BaseModel):
    type: Literal["clarify"] = "clarify"
    question: str


class FinalEvent(BaseModel):
    type: Literal["final"] = "final"


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    code: str  # "max_iter" | "provider_rate_limited" | ...
    message: str


StreamEvent = Union[TokenEvent, ToolStartEvent, ToolResultEvent, ClarifyEvent, FinalEvent, ErrorEvent]
