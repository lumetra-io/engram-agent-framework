"""Unit tests for the EngramClient REST surface (mocked).

Run with:
    pip install -e .[dev]
    pytest -q
"""

from __future__ import annotations

import httpx
import pytest

from agent_framework_engram.client import EngramClient, EngramError


def _mock_transport(handler):
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_store_memory_posts_content() -> None:
    async def handler(req: httpx.Request) -> httpx.Response:
        assert req.method == "POST"
        assert req.url.path == "/v1/buckets/b/memories"
        assert req.headers["authorization"] == "Bearer test"
        import json
        body = json.loads(req.content.decode())
        assert body == {"content": "hello"}
        return httpx.Response(201, json={"memory_id": "m1", "id": "m1"})

    async with httpx.AsyncClient(transport=_mock_transport(handler)) as h:
        c = EngramClient(api_key="test", http_client=h)
        r = await c.store_memory("hello", "b")
        assert r["memory_id"] == "m1"


@pytest.mark.asyncio
async def test_query_uses_query_field_not_question() -> None:
    async def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/v1/query"
        import json
        body = json.loads(req.content.decode())
        assert "query" in body and "question" not in body
        assert body["buckets"] == ["b"]
        return httpx.Response(200, json={"success": True, "answer": "ok"})

    async with httpx.AsyncClient(transport=_mock_transport(handler)) as h:
        c = EngramClient(api_key="test", http_client=h)
        r = await c.query_memory("what?", "b")
        assert r["answer"] == "ok"


@pytest.mark.asyncio
async def test_list_and_delete_paths() -> None:
    seen: list[tuple[str, str]] = []

    async def handler(req: httpx.Request) -> httpx.Response:
        seen.append((req.method, req.url.path))
        return httpx.Response(200, json={"memories": [], "buckets": [], "success": True})

    async with httpx.AsyncClient(transport=_mock_transport(handler)) as h:
        c = EngramClient(api_key="test", http_client=h)
        await c.list_buckets(limit=5)
        await c.list_memories("b", limit=5)
        await c.delete_memory("b", "mid")
        await c.clear_bucket("b")

    assert ("GET", "/v1/buckets") in seen
    assert ("GET", "/v1/buckets/b/memories") in seen
    assert ("DELETE", "/v1/buckets/b/memories/mid") in seen
    assert ("DELETE", "/v1/buckets/b/memories") in seen


@pytest.mark.asyncio
async def test_error_status_raises() -> None:
    async def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="bad key")

    async with httpx.AsyncClient(transport=_mock_transport(handler)) as h:
        c = EngramClient(api_key="test", http_client=h)
        with pytest.raises(EngramError):
            await c.store_memory("x", "b")


def test_missing_key_raises(monkeypatch) -> None:
    monkeypatch.delenv("ENGRAM_API_KEY", raising=False)
    with pytest.raises(ValueError):
        EngramClient()
