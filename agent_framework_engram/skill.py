"""Engram tools: bundle of ``@tool``-decorated functions for an Agent.

This is the recommended extension point because it gives the model
*first-class* tool access to memory operations — the LLM decides when to
recall context and when to persist new facts, rather than the framework
making that decision for it.

.. note::

    This module used to expose :class:`EngramSkill`. It has been renamed
    to :class:`EngramTools` to avoid collision with Microsoft Agent
    Framework's own ``Skill`` primitive (the SKILL.md domain-knowledge
    package per the ``agentskills.io`` spec). The old name is still
    importable as a deprecated alias.

Example
-------

>>> from agent_framework import Agent
>>> from agent_framework.openai import OpenAIChatClient
>>> from agent_framework_engram import EngramTools
>>>
>>> tools = EngramTools(bucket="my-agent")  # picks up ENGRAM_API_KEY
>>> agent = Agent(
...     client=OpenAIChatClient(),
...     name="assistant",
...     instructions=(
...         "You have durable memory via the engram_* tools. "
...         "Call engram_query_memory before answering questions about the "
...         "user, and engram_store_memory whenever they share a new fact."
...     ),
...     tools=tools.tools,
... )
"""

from __future__ import annotations

import os
import warnings
from typing import Annotated, Any

try:  # pragma: no cover - exercised only when agent-framework is installed
    from agent_framework import tool as _af_tool
except ImportError:  # pragma: no cover - keep import-time errors helpful
    _af_tool = None  # type: ignore[assignment]

from agent_framework_engram.client import EngramClient


def _require_framework() -> None:
    if _af_tool is None:
        raise ImportError(
            "agent-framework is not installed. Install it with "
            "`pip install agent-framework>=1.5` to use EngramTools."
        )


class EngramTools:
    """A bundle of Engram memory tools, bound to a single bucket.

    Parameters
    ----------
    bucket:
        Logical namespace for this agent's memories. One bucket per agent
        (or per agent+user pair) is the recommended pattern.
    api_key:
        Engram API key. Falls back to ``ENGRAM_API_KEY``.
    base_url:
        REST base URL override (defaults to ``https://api.lumetra.io``).
    client:
        Optional pre-constructed :class:`EngramClient` to share connection
        pooling across tool bundles.
    include:
        Optional whitelist of tool names to expose. Defaults to all six.
        Useful if you want to expose recall but hide destructive ops.
    """

    ALL_TOOLS = (
        "store_memory",
        "query_memory",
        "list_memories",
        "delete_memory",
        "clear_bucket",
        "list_buckets",
    )

    def __init__(
        self,
        bucket: str,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        client: EngramClient | None = None,
        include: tuple[str, ...] | None = None,
    ) -> None:
        _require_framework()
        if not bucket:
            raise ValueError("bucket is required")
        self.bucket = bucket
        self.client = client or EngramClient(
            api_key=api_key or os.environ.get("ENGRAM_API_KEY"),
            base_url=base_url,
        )
        self._include = set(include) if include else set(self.ALL_TOOLS)
        unknown = self._include - set(self.ALL_TOOLS)
        if unknown:
            raise ValueError(f"Unknown tool names in include: {sorted(unknown)}")

        self._tools = self._build_tools()

    # -- public --------------------------------------------------------

    @property
    def tools(self) -> list[Any]:
        """List of decorated tool callables for ``ChatAgent(tools=...)``."""
        return list(self._tools)

    async def aclose(self) -> None:
        await self.client.aclose()

    # -- internal ------------------------------------------------------

    def _build_tools(self) -> list[Any]:
        c = self.client
        bucket = self.bucket
        tools: list[Any] = []

        if "store_memory" in self._include:

            @_af_tool(
                name="engram_store_memory",
                description=(
                    "Persist one atomic fact to durable agent memory. Call "
                    "this whenever the user shares a preference, plan, "
                    "identity detail, or decision worth remembering across "
                    "future conversations."
                ),
            )
            async def engram_store_memory(
                content: Annotated[
                    str,
                    "One declarative fact in plain English. E.g. "
                    "'User prefers metric units.'",
                ],
            ) -> str:
                r = await c.store_memory(content, bucket)
                mid = r.get("memory_id") or r.get("id") or "(unknown)"
                return f"stored memory {mid} in bucket '{bucket}'"

            tools.append(engram_store_memory)

        if "query_memory" in self._include:

            @_af_tool(
                name="engram_query_memory",
                description=(
                    "Hybrid semantic + knowledge-graph retrieval over prior "
                    "memory. Call this BEFORE answering any question about "
                    "the user or earlier context."
                ),
            )
            async def engram_query_memory(
                query: Annotated[
                    str,
                    "Natural-language question to look up in memory.",
                ],
            ) -> str:
                r = await c.query_memory(query, bucket)
                ans = (r.get("answer") or "").strip()
                if not ans:
                    return "No relevant memories found."
                # Strip optional chain-of-thought prefix Engram emits.
                if "FINAL ANSWER:" in ans:
                    ans = ans.split("FINAL ANSWER:")[-1].strip()
                return ans

            tools.append(engram_query_memory)

        if "list_memories" in self._include:

            @_af_tool(
                name="engram_list_memories",
                description=(
                    "List recent raw memories in this bucket. Useful for "
                    "auditing or letting the user browse what's stored."
                ),
            )
            async def engram_list_memories(
                limit: Annotated[
                    int,
                    "Maximum number of memories to return (1-200).",
                ] = 25,
            ) -> str:
                limit = max(1, min(int(limit), 200))
                r = await c.list_memories(bucket, limit=limit)
                items = r.get("memories", [])
                if not items:
                    return f"No memories in bucket '{bucket}'."
                lines = [
                    f"- [{m.get('id', '?')[:8]}] {m.get('content', '')}"
                    for m in items
                ]
                return "\n".join(lines)

            tools.append(engram_list_memories)

        if "delete_memory" in self._include:

            @_af_tool(
                name="engram_delete_memory",
                description=(
                    "Delete a single memory by its ID. Use after the user "
                    "explicitly retracts a fact."
                ),
            )
            async def engram_delete_memory(
                memory_id: Annotated[
                    str,
                    "The UUID of the memory to delete (from list_memories).",
                ],
            ) -> str:
                await c.delete_memory(bucket, memory_id)
                return f"deleted memory {memory_id}"

            tools.append(engram_delete_memory)

        if "clear_bucket" in self._include:

            @_af_tool(
                name="engram_clear_bucket",
                description=(
                    "DESTRUCTIVE: wipe every memory in this bucket. Only "
                    "call after explicit user confirmation."
                ),
                approval_mode="always_require",
            )
            async def engram_clear_bucket() -> str:
                r = await c.clear_bucket(bucket)
                n = r.get("cleared_count", "?")
                return f"cleared {n} memories from bucket '{bucket}'"

            tools.append(engram_clear_bucket)

        if "list_buckets" in self._include:

            @_af_tool(
                name="engram_list_buckets",
                description=(
                    "List all buckets in the Engram tenant (read-only)."
                ),
            )
            async def engram_list_buckets(
                limit: Annotated[int, "Max buckets to return (1-200)."] = 50,
            ) -> str:
                limit = max(1, min(int(limit), 200))
                r = await c.list_buckets(limit=limit)
                items = r.get("buckets", [])
                if not items:
                    return "No buckets."
                return "\n".join(
                    f"- {b.get('bucket_name') or b.get('name')} "
                    f"({b.get('memory_count', 0)} memories)"
                    for b in items
                )

            tools.append(engram_list_buckets)

        return tools


def engram_tools(
    bucket: str,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    include: tuple[str, ...] | None = None,
) -> list[Any]:
    """Convenience helper mirroring the ``engram_*`` pattern used by our
    other framework integrations. Returns a plain list of tools you can
    splat into ``ChatAgent(tools=...)``.
    """
    return EngramTools(
        bucket, api_key=api_key, base_url=base_url, include=include
    ).tools


class EngramSkill(EngramTools):
    """Deprecated alias for :class:`EngramTools`.

    Renamed to avoid collision with Microsoft Agent Framework's own
    ``Skill`` primitive (SKILL.md domain-knowledge bundles). Will be
    removed in a future release.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        warnings.warn(
            "EngramSkill is deprecated and will be removed in a future "
            "release; use EngramTools instead. The rename avoids collision "
            "with Microsoft Agent Framework's Skill (SKILL.md) primitive.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(*args, **kwargs)
