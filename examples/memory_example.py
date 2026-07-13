"""ChainForge example: multi-turn conversation with memory."""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from chainforge.core.tool import tool
from chainforge.memory import BufferMemory
from chainforge.core.agent import Agent
from chainforge.providers import OpenAIProvider


@tool
def current_time(format: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Get the current date and time."""
    import datetime
    return datetime.datetime.now().strftime(format)


async def main():
    if not os.environ.get("OPENAI_API_KEY"):
        print("⚠️  Set OPENAI_API_KEY to run this example.")
        return

    memory = BufferMemory(max_messages=20)

    agent = Agent(
        llm=OpenAIProvider(model="gpt-4o-mini"),
        tools=[current_time],
        system_prompt="You are a helpful assistant with memory of our conversation.",
        temperature=0.5,
    )

    print("🤖 ChainForge Memory Demo (type 'exit' to quit)")
    print("=" * 50)

    while True:
        user_input = input("\n👤 ").strip()
        if user_input.lower() in ("exit", "quit"):
            break

        # Combine memory history with new message
        history = await memory.load()
        messages = history + [__import__("chainforge.core.message", fromlist=["Message"]).Message.user(user_input)]

        print("🤖 ", end="", flush=True)
        stream = await agent.run(messages)
        full_response = ""
        async for event in stream:
            if event.type == "text" and event.content:
                print(event.content, end="", flush=True)
                full_response += event.content
            elif event.type == "tool_call":
                print(f"\n🔧 [{event.data['name']}] ", end="", flush=True)
        print()

        # Save to memory
        await memory.save([__import__("chainforge.core.message", fromlist=["Message"]).Message.user(user_input)])
        await memory.save([
            __import__("chainforge.core.message", fromlist=["Message"]).Message.assistant(full_response)
        ])


if __name__ == "__main__":
    asyncio.run(main())
