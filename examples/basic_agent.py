"""ChainForge example: basic agent with weather and search tools.

Usage:
    python examples/basic_agent.py
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from chainforge.core.tool import tool
from chainforge.core.stream import StreamEvent


@tool
def get_weather(city: str, unit: str = "celsius") -> str:
    """Get the current weather for a city."""
    conditions = {
        "beijing": ("Sunny", 28),
        "shanghai": ("Cloudy", 25),
        "tokyo": ("Rainy", 22),
        "london": ("Foggy", 15),
        "new york": ("Clear", 26),
    }
    city_lower = city.lower()
    if city_lower in conditions:
        desc, temp = conditions[city_lower]
        temp_c = temp if unit == "celsius" else temp * 9 / 5 + 32
        unit_sym = "°C" if unit == "celsius" else "°F"
        return f"Weather in {city.title()}: {desc}, {temp_c:.0f}{unit_sym}"
    return f"Weather data not available for {city}"


@tool
def search(query: str) -> str:
    """Search for information on the web."""
    knowledge = {
        "chainforge": (
            "ChainForge is a next-generation AI agent framework. "
            "It is streaming-first, type-safe, and minimal. "
            "Built as a better alternative to LangChain."
        ),
        "python": "Python is a high-level, general-purpose programming language.",
    }
    for key, value in knowledge.items():
        if key in query.lower():
            return value
    return f"No results found for '{query}'."


async def main():
    from chainforge import Agent
    from chainforge.providers import OpenAIProvider

    if not os.environ.get("OPENAI_API_KEY"):
        print("⚠️  No OPENAI_API_KEY found. Running framework demo.")
        print()
        demo_framework()
        return

    agent = Agent(
        llm=OpenAIProvider(model="gpt-4o"),
        tools=[get_weather, search],
        system_prompt="You are a helpful assistant with weather and search capabilities.",
        temperature=0.3,
    )

    print("🤖 ChainForge Agent Demo")
    print("=" * 50)
    print()

    prompt = input("Enter your question (or press Enter for default): ").strip()
    if not prompt:
        prompt = "What's the weather in Beijing and Tokyo? Also, what is ChainForge?"
        print(f"Using default: {prompt}")

    print(f"\n👤 {prompt}")
    print("🤖 ", end="", flush=True)

    stream = await agent.run(prompt)
    async for event in stream:
        if event.type == "text" and event.content:
            print(event.content, end="", flush=True)
        elif event.type == "tool_call":
            print(f"\n🔧 Calling '{event.data['name']}'...")
            print("🤖 ", end="", flush=True)
        elif event.type == "tool_result":
            print(f"\n  └─ {event.data['content'][:60]}...")
            print("🤖 ", end="", flush=True)
        elif event.type == "error":
            print(f"\n❌ Error: {event.content}")

    print("\n\n✅ Done!")


def demo_framework():
    """Demonstrate framework features without API calls."""
    print("⚙️  ChainForge Framework Components")
    print("-" * 50)

    # Tool specs
    print("\n📋 Tool Schema (auto-generated):")
    for t in [get_weather, search]:
        spec = t.spec
        print(f"  • {spec.name}: {spec.description}")
        print(f"    Parameters: {list(spec.parameters.get('properties', {}).keys())}")

    # Stream events
    print("\n📡 Stream Events:")
    for event in [
        StreamEvent.text("Hello"),
        StreamEvent.tool_call("get_weather", {"city": "Beijing"}),
        StreamEvent.tool_result("get_weather", "Sunny, 28°C"),
        StreamEvent.text("It's sunny in Beijing at 28°C."),
        StreamEvent.done(),
    ]:
        icon = {"text": "💬", "tool_call": "🔧", "tool_result": "📎", "done": "✅", "error": "❌", "status": "ℹ️"}
        print(f"  {icon.get(event.type.value, '•')} {event.type.value}: {str(event.content or event.data)[:50]}")

    # Pipeline
    print("\n🔗 Pipeline:")
    from chainforge.core.pipeline import Pipeline

    pipe = Pipeline("upper_bracket", steps=[
        lambda x: x.upper(),
        lambda x: f"[{x}]",
    ])
    result = pipe("hello chainforge")
    print(f"  'hello chainforge' → '{result}'")

    # Middleware
    print("\n🔄 Middleware: composable hooks for tracing, retry, logging")
    print("  • Built-in: ConsoleTracer, tracing_middleware")
    print("  • Protocol: any async function of (messages, ctx, next_handler) → stream")

    # MCP
    print("\n🔌 MCP Client: connect to Model Context Protocol servers")
    print("  • Dynamic tool discovery via stdio or SSE")
    print("  • Use any MCP server's tools as native ChainForge tools")

    print("\n✅ Demo complete! Set OPENAI_API_KEY to run with real LLM calls.")


if __name__ == "__main__":
    asyncio.run(main())
