"""Minimal end-to-end example using EngramSkill with a ChatAgent.

Requires:
    pip install agent-framework agent-framework-engram
    export OPENAI_API_KEY=sk-...
    export ENGRAM_API_KEY=eng_live_...
"""

from __future__ import annotations

import asyncio

from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient

from agent_framework_engram import EngramSkill


async def main() -> None:
    skill = EngramSkill(bucket="agent-framework-demo")

    agent = Agent(
        client=OpenAIChatClient(),
        name="memory-demo",
        instructions=(
            "You have durable memory across conversations via the engram_* "
            "tools. Always call engram_query_memory before answering "
            "questions about the user, and engram_store_memory whenever "
            "the user shares a new preference, plan, or identity detail."
        ),
        tools=skill.tools,
    )

    print(await agent.run("Hi, I'm Jacob and I prefer concise replies."))
    print(await agent.run("What do you remember about me?"))

    await skill.aclose()


if __name__ == "__main__":
    asyncio.run(main())
