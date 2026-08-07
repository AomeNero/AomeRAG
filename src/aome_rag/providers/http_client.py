"""共享异步 HTTP 客户端：429/5xx 自动重试退避。"""

from __future__ import annotations

import asyncio
import random
from collections.abc import AsyncIterator

import httpx

from .errors import ProviderError, RateLimitError


class HttpRetryClient:
    """httpx.AsyncClient 的薄封装，对 429/5xx 做有上限的重试。

    `transport` 可注入以便测试（httpx.MockTransport）。测试里设 `backoff_initial=0.0`
    跳过真实等待。
    """

    def __init__(
        self,
        *,
        base_url: str,
        headers: dict[str, str],
        max_retries: int = 3,
        backoff_initial: float = 0.5,
        backoff_max: float = 8.0,
        timeout: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._headers = headers
        self._max_retries = max_retries
        self._bo_initial = backoff_initial
        self._bo_max = backoff_max
        self._client = httpx.AsyncClient(timeout=timeout, transport=transport)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _sleep(self, attempt: int) -> None:
        delay = min(self._bo_initial * (2 ** (attempt - 1)), self._bo_max)
        delay = delay * (0.5 + random.random() * 0.5)  # full jitter
        if delay > 0:
            await asyncio.sleep(delay)

    @staticmethod
    def _retryable(status: int) -> bool:
        return status == 429 or 500 <= status < 600

    async def post_json(self, path: str, payload: dict) -> dict:
        url = self._base + path
        for attempt in range(self._max_retries + 1):
            resp = await self._client.post(url, json=payload, headers=self._headers)
            status = resp.status_code
            if self._retryable(status):
                if attempt < self._max_retries:
                    await self._sleep(attempt + 1)
                    continue
                if status == 429:
                    raise RateLimitError(f"rate limited after {attempt + 1} attempts")
                raise ProviderError(f"upstream error {status}")
            resp.raise_for_status()
            return resp.json()
        raise ProviderError("retries exhausted")  # unreachable

    async def post_stream(self, path: str, payload: dict) -> AsyncIterator[str]:
        """从流式 POST 产出原始响应行。只在流开始前重试
        （一旦有字节流动就无法续传）。"""
        url = self._base + path
        for attempt in range(self._max_retries + 1):
            req = self._client.build_request("POST", url, json=payload, headers=self._headers)
            resp = await self._client.send(req, stream=True)
            status = resp.status_code
            if self._retryable(status):
                await resp.aclose()
                if attempt < self._max_retries:
                    await self._sleep(attempt + 1)
                    continue
                if status == 429:
                    raise RateLimitError(f"rate limited after {attempt + 1} attempts")
                raise ProviderError(f"upstream error {status}")
            try:
                async for line in resp.aiter_lines():
                    yield line
            finally:
                await resp.aclose()
            return
