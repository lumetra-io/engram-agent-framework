"""Thin async REST client for the Engram memory service.

Kept dependency-free beyond ``httpx`` so it can be reused by both the skill
and middleware extension points without dragging in the rest of the
``agent-framework`` runtime.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

DEFAULT_BASE_URL = "https://api.lumetra.io"
# Query endpoint can take 30-60s on cold cache; default generously.
DEFAULT_TIMEOUT = 90.0


class EngramError(RuntimeError):
    """Raised when the Engram REST API returns a non-2xx response."""


class EngramClient:
    """Async client for the Engram REST API.

    Parameters
    ----------
    api_key:
        Engram API key, e.g. ``eng_live_...``. Falls back to the
        ``ENGRAM_API_KEY`` environment variable.
    base_url:
        REST base URL. Falls back to ``ENGRAM_BASE_URL`` then
        ``https://api.lumetra.io``.
    timeout:
        Per-request timeout in seconds.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        key = api_key or os.environ.get("ENGRAM_API_KEY")
        if not key:
            raise ValueError(
                "Engram API key required: pass api_key=... or set ENGRAM_API_KEY"
            )
        self._api_key = key
        self._base_url = (
            base_url or os.environ.get("ENGRAM_BASE_URL") or DEFAULT_BASE_URL
        ).rstrip("/")
        self._timeout = timeout
        self._owned_client = http_client is None
        self._client = http_client or httpx.AsyncClient(timeout=timeout)

    # -- lifecycle -----------------------------------------------------

    async def aclose(self) -> None:
        if self._owned_client:
            await self._client.aclose()

    async def __aenter__(self) -> "EngramClient":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.aclose()

    # -- internal ------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "User-Agent": "agent-framework-engram/0.1.1",
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        resp = await self._client.request(
            method, url, headers=self._headers(), json=json, params=params
        )
        if resp.status_code >= 400:
            raise EngramError(
                f"Engram {method} {path} -> {resp.status_code}: {resp.text[:500]}"
            )
        if resp.status_code == 204 or not resp.content:
            return {}
        try:
            return resp.json()
        except ValueError:
            return {"raw": resp.text}

    # -- REST surface --------------------------------------------------

    async def store_memory(self, content: str, bucket: str) -> dict[str, Any]:
        """POST /v1/buckets/{bucket}/memories"""
        return await self._request(
            "POST", f"/v1/buckets/{bucket}/memories", json={"content": content}
        )

    async def query_memory(self, query: str, bucket: str) -> dict[str, Any]:
        """POST /v1/query"""
        return await self._request(
            "POST", "/v1/query", json={"query": query, "buckets": [bucket]}
        )

    async def list_buckets(
        self, *, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        """GET /v1/buckets"""
        return await self._request(
            "GET", "/v1/buckets", params={"limit": limit, "offset": offset}
        )

    async def list_memories(
        self, bucket: str, *, limit: int = 50
    ) -> dict[str, Any]:
        """GET /v1/buckets/{bucket}/memories"""
        return await self._request(
            "GET", f"/v1/buckets/{bucket}/memories", params={"limit": limit}
        )

    async def delete_memory(
        self, bucket: str, memory_id: str
    ) -> dict[str, Any]:
        """DELETE /v1/buckets/{bucket}/memories/{memory_id}"""
        return await self._request(
            "DELETE", f"/v1/buckets/{bucket}/memories/{memory_id}"
        )

    async def clear_bucket(self, bucket: str) -> dict[str, Any]:
        """DELETE /v1/buckets/{bucket}/memories"""
        return await self._request("DELETE", f"/v1/buckets/{bucket}/memories")
