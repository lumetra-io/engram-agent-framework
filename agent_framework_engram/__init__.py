"""Engram (Lumetra) integration for the Microsoft Agent Framework.

Two extension points are exported:

* :class:`EngramSkill` - a bundle of ``@ai_function`` tools you pass straight
  to ``ChatAgent(..., tools=skill.tools)``. This gives the LLM first-class
  ability to ``store_memory`` / ``query_memory`` / ``list_memories`` /
  ``delete_memory`` / ``clear_bucket`` / ``list_buckets`` against your
  Engram tenant. This is the recommended path.

* :class:`EngramMiddleware` - an ``agent_middleware``-flavoured callable that
  transparently recalls relevant memories before each agent turn and
  (optionally) auto-stores the user's most recent message after each turn.
  Use this when you don't want to expose memory ops to the model as tools.

Both accept either an explicit ``api_key`` or fall back to the
``ENGRAM_API_KEY`` environment variable. The default REST base is
``https://api.lumetra.io`` and can be overridden with ``base_url`` or the
``ENGRAM_BASE_URL`` environment variable (for self-hosted deployments).
"""

from agent_framework_engram.client import EngramClient
from agent_framework_engram.middleware import EngramMiddleware
from agent_framework_engram.skill import EngramSkill

__all__ = ["EngramClient", "EngramMiddleware", "EngramSkill"]
__version__ = "0.1.0"
