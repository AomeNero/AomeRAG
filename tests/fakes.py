"""Test doubles. FakeProvider implements the LLMProvider Protocol with a scriptable
sequence of responses / delta lists, so the agent loop can be tested with zero network."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from aome_rag.providers.base import LLMDelta, LLMResponse, ToolSchema
from aome_rag.providers.messages import Message


class FakeProvider:
    name = "fake"

    def __init__(self) -> None:
        # Each entry is either an LLMResponse (for complete()) or a list[LLMDelta] (for stream()).
        self._script: list[Any] = []

    def enqueue(self, item: LLMResponse | list[LLMDelta]) -> None:
        self._script.append(item)

    async def complete(
        self,
        messages: list[Message],
        tools: list[ToolSchema],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        return self._script.pop(0)

    def stream(
        self,
        messages: list[Message],
        tools: list[ToolSchema],
        *,
        model: str | None = None,
        temperature: float = 0.0,
    ) -> AsyncIterator[LLMDelta]:
        return self._stream()

    async def _stream(self) -> AsyncIterator[LLMDelta]:
        for delta in self._script.pop(0):
            yield delta
