import httpx
import pytest

from aome_rag.providers.errors import ProviderError, RateLimitError
from aome_rag.providers.http_client import HttpRetryClient


async def test_post_json_retries_on_429_then_succeeds() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(429)
        return httpx.Response(200, json={"ok": True})

    client = HttpRetryClient(
        base_url="https://x.example",
        headers={},
        transport=httpx.MockTransport(handler),
        backoff_initial=0.0,
    )
    try:
        data = await client.post_json("/p", {})
    finally:
        await client.aclose()
    assert data == {"ok": True}
    assert calls["n"] == 3


async def test_post_json_rate_limited_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429)

    client = HttpRetryClient(
        base_url="https://x.example",
        headers={},
        transport=httpx.MockTransport(handler),
        max_retries=2,
        backoff_initial=0.0,
    )
    try:
        with pytest.raises(RateLimitError):
            await client.post_json("/p", {})
    finally:
        await client.aclose()


async def test_post_stream_yields_lines() -> None:
    body = b"data: {\"a\":1}\n\ndata: [DONE]\n\n"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    client = HttpRetryClient(
        base_url="https://x.example",
        headers={},
        transport=httpx.MockTransport(handler),
        backoff_initial=0.0,
    )
    lines: list[str] = []
    try:
        async for line in client.post_stream("/p", {}):
            lines.append(line)
    finally:
        await client.aclose()
    assert lines[0].startswith("data:")
    # aiter_lines yields the blank SSE separators too; the adapter filters non-data lines.
    assert any(ln.strip() == "data: [DONE]" for ln in lines)


async def test_post_json_500_then_ok() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(500) if calls["n"] == 1 else httpx.Response(200, json={"ok": True})

    client = HttpRetryClient(
        base_url="https://x.example",
        headers={},
        transport=httpx.MockTransport(handler),
        backoff_initial=0.0,
    )
    try:
        data = await client.post_json("/p", {})
    finally:
        await client.aclose()
    assert data == {"ok": True}
    assert calls["n"] == 2
