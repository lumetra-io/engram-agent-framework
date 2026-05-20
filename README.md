# agent-framework-engram

Durable memory for [Microsoft Agent Framework](https://github.com/microsoft/agent-framework) agents, powered by [Engram](https://lumetra.io) — Lumetra's memory service for AI agents.

Ships two extension points so you can pick whichever fits your architecture:

| Extension point   | Class             | What it does                                                                                        |
| ----------------- | ----------------- | --------------------------------------------------------------------------------------------------- |
| **Skill (tools)** | `EngramSkill`     | Exposes `engram_store_memory`, `engram_query_memory`, etc. as first-class `@ai_function` tools.     |
| **Middleware**    | `EngramMiddleware`| Transparently recalls relevant memories before each turn and auto-stores the user message after.    |

The Skill path is recommended — it lets the model itself decide when to recall and persist, which is the strength of Agent Framework's function-tool loop.

## Install

```bash
pip install agent-framework-engram
```

Requires `agent-framework>=1.5` and Python 3.10+.

Get an Engram API key at <https://lumetra.io>. Export it:

```bash
export ENGRAM_API_KEY=eng_live_...
```

## Quick start — Skill (recommended)

```python
import asyncio
from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient
from agent_framework_engram import EngramSkill


async def main() -> None:
    skill = EngramSkill(bucket="my-agent")  # ENGRAM_API_KEY from env

    agent = Agent(
        client=OpenAIChatClient(),
        name="assistant",
        instructions=(
            "You have durable memory across conversations via the engram_* "
            "tools. Call engram_query_memory before answering questions "
            "about the user, and engram_store_memory whenever the user "
            "shares a new preference or fact."
        ),
        tools=skill.tools,
    )

    print(await agent.run("Remember that I prefer dark mode and metric units."))
    print(await agent.run("What do you remember about my UI preferences?"))


asyncio.run(main())
```

## Quick start — Middleware (transparent)

```python
import asyncio
from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient
from agent_framework_engram import EngramMiddleware


async def main() -> None:
    agent = Agent(
        client=OpenAIChatClient(),
        name="assistant",
        instructions="You are a helpful assistant with long-term memory.",
        middleware=[EngramMiddleware(bucket="my-agent")],
    )

    print(await agent.run("Hi, my name is Jacob."))
    print(await agent.run("What's my name?"))


asyncio.run(main())
```

## Configuration

| Argument          | Env var               | Default                       |
| ----------------- | --------------------- | ----------------------------- |
| `api_key`         | `ENGRAM_API_KEY`      | *required*                    |
| `base_url`        | `ENGRAM_BASE_URL`     | `https://api.lumetra.io`      |
| `bucket`          | —                     | *required*                    |

For multi-tenant deployments, use one bucket per user (e.g. `f"user-{user_id}"`).

## Tools exposed by `EngramSkill`

| Tool                    | Maps to                                                |
| ----------------------- | ------------------------------------------------------ |
| `engram_store_memory`   | `POST /v1/buckets/{bucket}/memories`                   |
| `engram_query_memory`   | `POST /v1/query`                                       |
| `engram_list_memories`  | `GET  /v1/buckets/{bucket}/memories`                   |
| `engram_delete_memory`  | `DELETE /v1/buckets/{bucket}/memories/{memory_id}`     |
| `engram_clear_bucket`   | `DELETE /v1/buckets/{bucket}/memories`                 |
| `engram_list_buckets`   | `GET  /v1/buckets`                                     |

Restrict with `EngramSkill(bucket=..., include=("store_memory", "query_memory"))` if you only want recall/persist (no destructive ops).

## Self-hosted Engram

```python
EngramSkill(bucket="x", base_url="https://engram.your-corp.internal")
```

## License

MIT — see [LICENSE](LICENSE). Privacy notes in [PRIVACY.md](PRIVACY.md).
