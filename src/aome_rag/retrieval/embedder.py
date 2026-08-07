"""Ollama 嵌入：bge-m3 dense 向量，async HTTP，信号量限并发。"""

from __future__ import annotations

import asyncio

import httpx


class OllamaEmbedder:
    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        sem: asyncio.Semaphore | None = None,
        timeout: float = 60.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._url = base_url.rstrip("/") + "/api/embed"
        self._model = model
        self._sem = sem
        self._client = client or httpx.AsyncClient(timeout=timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _post(self, texts: list[str]) -> list[list[float]]:
        if self._sem is not None:
            await self._sem.acquire()
        try:
            resp = await self._client.post(
                self._url, json={"model": self._model, "input": texts}
            )
            resp.raise_for_status()
            data = resp.json()
            embeddings = data.get("embeddings")
            if embeddings is None and "embedding" in data:  # older single-text shape
                embeddings = [data["embedding"]]
            return embeddings
        finally:
            if self._sem is not None:
                self._sem.release()

    async def embed(self, text: str) -> list[float]:
        return (await self._post([text]))[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return await self._post(texts)
