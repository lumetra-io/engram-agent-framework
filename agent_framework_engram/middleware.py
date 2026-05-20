"""Agent-level middleware that wires Engram into every turn transparently.

Pick this when you do *not* want to expose memory ops to the model as
tools — e.g. you trust the framework to decide what to recall, and you
want every user turn auto-archived without the model thinking about it.

The middleware:

1. **Before each agent turn**, queries Engram with the user's latest
   message and prepends the recalled context as a system message in
   ``context.messages``.
2. **After each agent turn** (i.e. after ``call_next()`` returns),
   optionally stores the user's message as a new memory (controlled by
   ``auto_store``).

Example
-------

>>> from agent_framework import Agent
>>> from agent_framework.openai import OpenAIChatClient
>>> from agent_framework_engram import EngramMiddleware
>>>
>>> agent = Agent(
...     client=OpenAIChatClient(),
...     name="assistant",
...     middleware=[EngramMiddleware(bucket="my-agent")],
... )
"""

from __future__ import annotations

import os
from typing import Any

try:  # pragma: no cover - exercised only when agent-framework is installed
    from agent_framework import AgentMiddleware as _AgentMiddleware  # type: ignore
except ImportError:  # pragma: no cover
    _AgentMiddleware = object  # type: ignore[misc, assignment]

from agent_framework_engram.client import EngramClient

_SYSTEM_TEMPLATE = (
    "Relevant durable memory recalled for this turn (source: Engram):\n"
    "{recalled}\n"
    "Use this context if helpful. If it conflicts with the user's latest "
    "message, prefer the user's latest message."
)


class EngramMiddleware(_AgentMiddleware):  # type: ignore[misc]
    """Agent middleware that recalls + (optionally) auto-stores memories.

    Subclasses :class:`agent_framework.AgentMiddleware` and implements
    ``process(context, call_next)`` per the framework's contract.

    Parameters
    ----------
    bucket:
        Engram bucket to use for this agent.
    api_key:
        Engram API key. Falls back to ``ENGRAM_API_KEY``.
    base_url:
        Optional REST base override.
    auto_store:
        If True (default), persist the user's latest message as a memory
        after each turn completes.
    auto_recall:
        If True (default), query Engram before each turn and inject the
        result as a system message.
    client:
        Optional pre-built :class:`EngramClient` to share with a skill.

    Usage::

        agent = Agent(
            client=chat_client,
            middleware=[EngramMiddleware(bucket="x")],
        )
    """

    def __init__(
        self,
        bucket: str,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        auto_store: bool = True,
        auto_recall: bool = True,
        client: EngramClient | None = None,
    ) -> None:
        if _AgentMiddleware is object:
            raise ImportError(
                "agent-framework is not installed. Install it with "
                "`pip install agent-framework>=1.5` to use EngramMiddleware."
            )
        if not bucket:
            raise ValueError("bucket is required")
        self.bucket = bucket
        self.auto_store = auto_store
        self.auto_recall = auto_recall
        self.client = client or EngramClient(
            api_key=api_key or os.environ.get("ENGRAM_API_KEY"),
            base_url=base_url,
        )

    async def aclose(self) -> None:
        await self.client.aclose()

    # ----- AgentMiddleware contract -----------------------------------

    async def process(self, context: Any, call_next: Any) -> None:
        """Implements ``AgentMiddleware.process``.

        ``context`` exposes ``messages`` (the incoming chat history); we
        treat the most recent ``user`` role entry as the turn's query.
        Per the framework contract we do not return anything; we mutate
        ``context.messages`` in place and rely on ``call_next()`` to
        populate ``context.result``.
        """
        latest = _latest_user_text(context)

        if self.auto_recall and latest:
            try:
                recalled = await self._recall(latest)
                if recalled:
                    _prepend_system(
                        context, _SYSTEM_TEMPLATE.format(recalled=recalled)
                    )
            except Exception:  # pragma: no cover - never break the turn
                pass

        await call_next()

        if self.auto_store and latest:
            try:
                await self.client.store_memory(latest, self.bucket)
            except Exception:  # pragma: no cover
                pass

    async def _recall(self, query: str) -> str:
        r = await self.client.query_memory(query, self.bucket)
        ans = (r.get("answer") or "").strip()
        if "FINAL ANSWER:" in ans:
            ans = ans.split("FINAL ANSWER:")[-1].strip()
        return ans


# ---------------------------------------------------------------------
# Best-effort accessors for the framework's context object. We avoid
# importing concrete message classes from agent_framework so the module
# imports cleanly even without that dep installed (e.g. during packaging)
# and is resilient to minor shape drift across point releases.
# ---------------------------------------------------------------------


def _latest_user_text(context: Any) -> str | None:
    msgs = getattr(context, "messages", None)
    if not msgs:
        return None
    try:
        iterable = list(msgs)
    except TypeError:
        return None
    for m in reversed(iterable):
        role = getattr(m, "role", None) or (
            m.get("role") if isinstance(m, dict) else None
        )
        if role and str(role).lower() not in ("user", "role.user"):
            continue
        text = (
            getattr(m, "text", None)
            or getattr(m, "content", None)
            or (m.get("content") if isinstance(m, dict) else None)
        )
        if isinstance(text, list):  # content-parts style
            parts = []
            for p in text:
                t = getattr(p, "text", None) or (
                    p.get("text") if isinstance(p, dict) else None
                )
                if t:
                    parts.append(t)
            text = "\n".join(parts) if parts else None
        if text:
            return str(text)
    return None


def _prepend_system(context: Any, text: str) -> None:
    """Insert a system message at the head of ``context.messages``.

    We try the framework's ``ChatMessage`` first, then fall back to a
    plain ``Message``-shaped dict; if neither works we silently no-op
    rather than crash the turn.
    """
    msgs = getattr(context, "messages", None)
    if msgs is None:
        return
    sys_msg: Any
    try:
        from agent_framework import ChatMessage, Role  # type: ignore

        sys_msg = ChatMessage(role=Role.SYSTEM, text=text)
    except Exception:
        try:
            from agent_framework import Message, Role  # type: ignore

            sys_msg = Message(role=Role.SYSTEM, content=text)  # type: ignore[call-arg]
        except Exception:
            sys_msg = {"role": "system", "content": text}
    try:
        msgs.insert(0, sys_msg)
    except Exception:
        try:
            context.messages = [sys_msg, *msgs]
        except Exception:
            return
