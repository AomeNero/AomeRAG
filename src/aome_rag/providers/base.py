"""LLM provider Protocol + response/delta shapes."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Literal, Protocol, TypedDict, runtime_checkable, Union

from pydantic import BaseModel

from .messages import Message


class ToolFunctionDef(TypedDict):
    name: str
    description: str
    parameters: dict  # JSON Schema


class ToolSchema(TypedDict):
    type: Literal["function"]
    function: ToolFunctionDef


class TokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0


class LLMResponse(BaseModel):
    message: Message
    finish_reason: str  # "stop" | "tool_use" | "length" | ...
    usage: TokenUsage | None = None


# ---- streaming deltas (tool args arrive as JSON fragments and are accumulated by index) ----
class TextDelta(BaseModel):
    type: Literal["text"] = "text"
    text: str


class ToolCallDelta(BaseModel):
    type: Literal["tool_call"] = "tool_call"
    index: int
    id: str | None = None
    name: str | None = None
    arguments_chunk: str = ""


class Finish(BaseModel):
    type: Literal["finish"] = "finish"
    finish_reason: str
    usage: TokenUsage | None = None


LLMDelta = Union[TextDelta, ToolCallDelta, Finish]


@runtime_checkable
class LLMProvider(Protocol):
    name: str

    async def complete(
        self,
        messages: list[Message],
        tools: list[ToolSchema],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> LLMResponse: ...

    def stream(
        self,
        messages: list[Message],
        tools: list[ToolSchema],
        *,
        model: str | None = None,
        temperature: float = 0.0,
    ) -> AsyncIterator[LLMDelta]: ...
