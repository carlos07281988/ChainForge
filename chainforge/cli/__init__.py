"""ChainForge CLI — project scaffolding and utilities."""

import argparse
import sys

from chainforge._version import __version__


def main():
    parser = argparse.ArgumentParser(
        prog="chainforge",
        description="ChainForge — next-generation agent framework CLI",
    )
    parser.add_argument("--version", action="version", version=f"chainforge {__version__}")

    sub = parser.add_subparsers(dest="command", help="Available commands")

    # chainforge init
    init_parser = sub.add_parser("init", help="Scaffold a new ChainForge project")
    init_parser.add_argument("name", help="Project name")
    init_parser.add_argument("--dir", default=".", help="Target directory (default: current)")

    # chainforge quickstart
    qs_parser = sub.add_parser("quickstart", help="Generate a minimal agent script")
    qs_parser.add_argument("--provider", default="openai", choices=["openai", "anthropic", "google"],
                           help="LLM provider to use")

    args = parser.parse_args()

    if args.command == "init":
        _scaffold_project(args.name, args.dir)
    elif args.command == "quickstart":
        _generate_quickstart(args.provider)
    else:
        parser.print_help()


def _scaffold_project(name: str, target_dir: str):
    """Create a new ChainForge project with basic structure."""
    import os
    from pathlib import Path

    base = Path(target_dir) / name
    if base.exists():
        print(f"❌ Directory '{base}' already exists.")
        sys.exit(1)

    (base / "agents").mkdir(parents=True)
    (base / "tools").mkdir()
    (base / "workflows").mkdir()
    (base / "tests").mkdir()

    (base / "__init__.py").write_text("")
    (base / "agents" / "__init__.py").write_text("")
    (base / "tools" / "__init__.py").write_text("")
    (base / "workflows" / "__init__.py").write_text("")
    (base / "tests" / "__init__.py").write_text("")

    (base / "config.py").write_text(f'''"""ChainForge project configuration."""

from chainforge import Agent
from chainforge.providers import OpenAIProvider

# Default LLM — set OPENAI_API_KEY in your environment
llm = OpenAIProvider(model="gpt-4o")

# Shared agent defaults
AGENT_DEFAULTS = {{
    "llm": llm,
    "max_iterations": 10,
    "temperature": 0.3,
}}
''')

    (base / "main.py").write_text(f'''"""ChainForge agent: {name}"""

import asyncio
from chainforge import Agent, tool
from chainforge.providers import OpenAIProvider


@tool
def greet(name: str) -> str:
    """Greet someone by name."""
    return f"Hello, {{name}}!"


async def main():
    agent = Agent(
        llm=OpenAIProvider(),
        tools=[greet],
        system_prompt="You are a friendly agent.",
    )

    result = await agent.run("Say hello to ChainForge!")
    async for event in result:
        if event.type == "text":
            print(event.content, end="", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
''')

    (base / "tests" / "test_basic.py").write_text(f'''"""Tests for {name}."""

import pytest
from chainforge import Agent


class FakeLLM:
    model = "fake"
    async def generate(self, messages, tools=None, **kwargs):
        from chainforge.core.llm import LLMResponse
        return LLMResponse(content="test")
    async def stream_generate(self, messages, tools=None, **kwargs):
        yield "test"


@pytest.mark.asyncio
async def test_agent_creation():
    agent = Agent(llm=FakeLLM())
    assert agent.max_iterations == 10
''')

    (base / ".env.example").write_text("# Copy to .env and fill in your API keys\nOPENAI_API_KEY=\nANTHROPIC_API_KEY=\nGOOGLE_API_KEY=\n")

    print(f"✅ ChainForge project '{name}' created at {base}")
    print(f"\n  cd {base}")
    print(f"  pip install chainforge")
    print(f"  python main.py")


def _generate_quickstart(provider: str):
    """Print a minimal quickstart script."""
    provider_import = {
        "openai": "from chainforge.providers import OpenAIProvider\nllm = OpenAIProvider()",
        "anthropic": "from chainforge.providers import AnthropicProvider\nllm = AnthropicProvider()",
        "google": "from chainforge.providers import GoogleProvider\nllm = GoogleProvider()",
    }
    script = f'''"""ChainForge Quickstart — {provider}"""

import asyncio
from chainforge import Agent, tool


@tool
def get_weather(city: str) -> str:
    """Get weather for a city."""
    return f"Weather in {{city}}: sunny, 25°C"


async def main():
    {provider_import[provider]}

    agent = Agent(llm=llm, tools=[get_weather])

    async for event in await agent.run("Weather in Beijing?"):
        if event.type == "text":
            print(event.content, end="", flush=True)


asyncio.run(main())
'''
    print(script)


if __name__ == "__main__":
    main()
