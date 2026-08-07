"""OpenAI 兼容适配器（DeepSeek / GLM / Qwen / Kimi）。"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import structlog

from .base import Finish, LLMDelta, LLMResponse, TextDelta, TokenUsage, ToolCallDelta
from .errors import ToolCallParseError
from .http_client import HttpRetryClient
from .messages import Message, TextBlock, ToolResultBlock, ToolUseBlock

_CHAT_PATH = "/chat/completions"

_log = structlog.get_logger()


def parse_tool_arguments(raw: str) -> dict[str, Any]:
    """解析工具调用的 `arguments` JSON 字符串。

    JSON 非法或不是对象时抛 ToolCallParseError。调用方（agent 循环）捕获后合成
    `is_error=True` 的工具结果，让模型据此自我修正。"""
    try:
        obj = json.loads(raw or "{}")
    except json.JSONDecodeError as e:  # pragma: no cover - exercised via tests
        raise ToolCallParseError(f"tool arguments not valid JSON: {e}") from e
    if not isinstance(obj, dict):
        raise ToolCallParseError("tool arguments must be a JSON object")
    return obj


def messages_to_openai(messages: list[Message]) -> list[dict[str, Any]]:
    """内部消息 → OpenAI chat-completions 线上格式。"""
    out: list[dict[str, Any]] = []
    for m in messages:
        if m.role in ("system", "user"):
            out.append({"role": m.role, "content": m.as_text()})
        elif m.role == "assistant":
            entry: dict[str, Any] = {"role": "assistant"}
            text = m.as_text()
            if text:
                entry["content"] = text
            tool_calls = [
                {
                    "id": b.id,
                    "type": "function",
                    "function": {
                        "name": b.name,
                        "arguments": json.dumps(b.arguments, ensure_ascii=False),
                    },
                }
                for b in m.blocks
                if isinstance(b, ToolUseBlock)
            ]
            if tool_calls:
                entry["tool_calls"] = tool_calls
            out.append(entry)
            # assistant 消息里可能内嵌工具结果（clarify 把结果持久化在 assistant 消息内）。
            # 展开成紧随其后的 "tool" 角色消息，保证每个 tool_calls 都有配对结果——
            # 否则 OpenAI 兼容 API 会因"有 tool_calls 无结果"拒绝整个对话（400），
            # 导致 clarify 后 agent 拿到空回答。
            for b in m.blocks:
                if isinstance(b, ToolResultBlock):
                    out.append(
                        {"role": "tool", "tool_call_id": b.tool_use_id, "content": b.content}
                    )
        elif m.role == "tool":
            # 一条内部工具消息可能携带多个结果 → 展开成 N 条 role:"tool" 消息。
            for b in m.blocks:
                if isinstance(b, ToolResultBlock):
                    out.append(
                        {"role": "tool", "tool_call_id": b.tool_use_id, "content": b.content}
                    )
    return out


def _choice_to_message(choice: dict[str, Any]) -> Message:
    msg = choice.get("message", {})
    blocks: list[Any] = []
    content = msg.get("content")
    if content:
        blocks.append(TextBlock(text=content))
    for tc in msg.get("tool_calls") or []:
        fn = tc.get("function", {})
        args = parse_tool_arguments(fn.get("arguments") or "{}")
        blocks.append(ToolUseBlock(id=tc["id"], name=fn["name"], arguments=args))
    return Message(role="assistant", blocks=blocks)


def _parse_usage(usage: dict[str, Any] | None) -> TokenUsage | None:
    if not usage:
        return None
    return TokenUsage(
        input_tokens=usage.get("prompt_tokens", 0),
        output_tokens=usage.get("completion_tokens", 0),
    )


def _normalize_finish(reason: str | None) -> str:
    if reason == "tool_calls":
        return "tool_use"
    return reason or "stop"


def response_to_llm_response(resp: dict[str, Any]) -> LLMResponse:
    """OpenAI 非流式响应 → 内部 LLMResponse。"""
    choice = resp["choices"][0]
    return LLMResponse(
        message=_choice_to_message(choice),
        finish_reason=_normalize_finish(choice.get("finish_reason")),
        usage=_parse_usage(resp.get("usage")),
    )


def parse_stream_chunk(obj: dict[str, Any]) -> list[LLMDelta]:
    """解析单个 SSE JSON 对象 → deltas。不累积工具参数；调用方按索引累积
    ToolCallDelta，在 Finish 时构建 ToolUseBlock。"""
    choices = obj.get("choices") or []
    if not choices:
        return []
    choice = choices[0]
    delta = choice.get("delta") or {}
    out: list[LLMDelta] = []
    content = delta.get("content")
    if content:
        out.append(TextDelta(text=content))
    for tc in delta.get("tool_calls") or []:
        fn = tc.get("function") or {}
        out.append(
            ToolCallDelta(
                index=tc.get("index", 0),
                id=tc.get("id"),
                name=fn.get("name"),
                arguments_chunk=fn.get("arguments") or "",
            )
        )
    reason = choice.get("finish_reason")
    if reason:
        out.append(Finish(finish_reason=_normalize_finish(reason)))
    return out


class OpenAICompatProvider:
    """基于 OpenAI 兼容 chat-completions 端点的 LLMProvider 实现。"""

    name = "openai-compat"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        http: HttpRetryClient | None = None,
        timeout: float = 60.0,
    ) -> None:
        self._model = model
        self._http = http or HttpRetryClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=timeout,
        )

    def _payload(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        *,
        temperature: float,
        max_tokens: int | None,
        stream: bool,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages_to_openai(messages),
            "temperature": temperature,
            "stream": stream,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        return payload

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        _log.info(
            "llm.complete", model=model or self._model,
            n_messages=len(messages), n_tools=len(tools),
        )
        data = await self._http.post_json(
            _CHAT_PATH,
            self._payload(
                messages, tools, temperature=temperature, max_tokens=max_tokens, stream=False
            ),
        )
        resp = response_to_llm_response(data)
        usage = resp.usage
        _log.info(
            "llm.complete.done", model=model or self._model,
            finish_reason=resp.finish_reason,
            input_tokens=usage.input_tokens if usage else None,
            output_tokens=usage.output_tokens if usage else None,
        )
        return resp

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        *,
        model: str | None = None,
        temperature: float = 0.0,
    ) -> AsyncIterator[LLMDelta]:
        _log.info(
            "llm.stream", model=model or self._model,
            n_messages=len(messages), n_tools=len(tools),
        )
        payload = self._payload(
            messages, tools, temperature=temperature, max_tokens=None, stream=True
        )
        async for line in self._http.post_stream(_CHAT_PATH, payload):
            line = line.strip()
            if not line.startswith("data:"):
                continue
            data = line[len("data:") :].strip()
            if data == "[DONE]":
                return
            try:
                obj = json.loads(data)
            except json.JSONDecodeError:
                continue
            for delta in parse_stream_chunk(obj):
                yield delta
