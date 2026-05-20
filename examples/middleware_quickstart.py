"""Minimal example using EngramMiddleware for transparent memory."""

from __future__ import annotations

import asyncio

from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient

from agent_framework_engram import EngramMiddleware


async def main() -> None:
    mw = EngramMiddleware(bucket="agent-framework-demo-mw")

    agent = Agent(
        client=OpenAIChatClient(),
        name="memory-demo",
        instructions="You are a helpful assistant with long-term memory.",
        middleware=[mw],
    )

    print(await agent.run("Hi, I'm Jacob and I prefer concise replies."))
    print(await agent.run("What's my name and how do I like replies?"))

    await mw.aclose()


if __name__ == "__main__":
    asyncio.run(main())
