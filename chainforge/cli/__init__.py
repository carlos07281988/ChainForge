"""ChainForge CLI — project scaffolding, skill management, and utilities."""

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

    # ── chainforge init ──────────────────────────────────────────────────
    init_parser = sub.add_parser("init", help="Scaffold a new ChainForge project")
    init_parser.add_argument("name", help="Project name")
    init_parser.add_argument("--dir", default=".", help="Target directory (default: current)")

    # ── chainforge quickstart ────────────────────────────────────────────
    qs_parser = sub.add_parser("quickstart", help="Generate a minimal agent script")
    qs_parser.add_argument("--provider", default="openai", choices=["openai", "anthropic", "google"],
                           help="LLM provider to use")

    # ── chainforge skill ─────────────────────────────────────────────────
    skill_parser = sub.add_parser("skill", help="Manage skills")
    skill_sub = skill_parser.add_subparsers(dest="skill_command")

    # skill list
    skill_sub.add_parser("list", help="List available skills")

    # skill add <path>
    add_skill = skill_sub.add_parser("add", help="Register a skill from a file/directory")
    add_skill.add_argument("path", help="Path to SKILL.md or directory of skills")

    # skill info <name>
    info_skill = skill_sub.add_parser("info", help="Show skill details")
    info_skill.add_argument("name", help="Skill name")

    args = parser.parse_args()

    if args.command == "init":
        _scaffold_project(args.name, args.dir)
    elif args.command == "quickstart":
        _generate_quickstart(args.provider)
    elif args.command == "skill":
        _handle_skill_command(args)
    else:
        parser.print_help()


def _handle_skill_command(args):
    """Handle skill subcommands."""
    from chainforge.skills import SkillRegistry

    registry = SkillRegistry()

    if args.skill_command == "list":
        registry.load_dir(".")
        skills = registry.list()
        if not skills:
            print("No skills found.")
            return
        print(f"{'Name':<24} {'Description':<48} {'Tags'}")
        print("-" * 90)
        for s in skills:
            tags = ", ".join(s.spec.tags) if s.spec.tags else ""
            print(f"{s.name:<24} {s.description[:46]:<48} {tags}")

    elif args.skill_command == "add":
        import os
        path = args.path
        if os.path.isfile(path) and path.endswith("SKILL.md"):
            from chainforge.skills.loader import load_skill_from_file
            skill = load_skill_from_file(path)
            registry.register(skill)
            print(f"✅ Registered skill: {skill.name}")
        elif os.path.isdir(path):
            skills = registry.load_dir(path)
            print(f"✅ Registered {len(skills)} skill(s) from {path}")
        else:
            print(f"❌ No SKILL.md found at {path}")

    elif args.skill_command == "info":
        from chainforge.skills.loader import load_skill_from_file
        name = args.name
        found = None
        # Try as file path first, then as registry name
        if name.endswith("SKILL.md") or "/" in name:
            try:
                found = load_skill_from_file(name)
            except FileNotFoundError:
                pass
        if found is None:
            registry.load_dir(".")
            found = registry.get(name)
        if found:
            print(f"Name:        {found.name}")
            print(f"Description: {found.description}")
            print(f"Version:     {found.spec.version}")
            print(f"Tags:        {', '.join(found.spec.tags) if found.spec.tags else '(none)'}")
            print(f"Tools:       {len(found.tools)}")
            print(f"\nInstructions:\n{found.instructions[:500]}")
        else:
            print(f"❌ Skill not found: {name}")

    else:
        print("Usage: chainforge skill {list|add|info}")


def _scaffold_project(name: str, target_dir: str):
    """Create a new ChainForge project with basic structure."""
    from pathlib import Path
    base = Path(target_dir) / name
    if base.exists():
        print(f"❌ Directory '{base}' already exists.")
        sys.exit(1)

    (base / "agents").mkdir(parents=True)
    (base / "tools").mkdir()
    (base / "skills").mkdir()
    (base / "workflows").mkdir()
    (base / "tests").mkdir()

    for d in ["", "agents", "tools", "skills", "workflows", "tests"]:
        (base / d / "__init__.py").write_text("")

    (base / "config.py").write_text(f'''"""ChainForge project configuration."""

from chainforge import Agent
from chainforge.providers import OpenAIProvider

llm = OpenAIProvider(model="gpt-4o")
AGENT_DEFAULTS = {{"llm": llm, "max_iterations": 10, "temperature": 0.3}}
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
    agent = Agent(llm=OpenAIProvider(), tools=[greet],
                  system_prompt="You are a friendly agent.")
    async for event in await agent.run("Say hello to ChainForge!"):
        if event.type == "text":
            print(event.content, end="", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
''')

    (base / "tests" / "test_basic.py").write_text(f'''"""Tests for {{name}}."""
import pytest
@pytest.mark.asyncio
async def test_agent(): pass
''')

    (base / ".env.example").write_text("OPENAI_API_KEY=\nANTHROPIC_API_KEY=\nGOOGLE_API_KEY=\n")
    print(f"✅ ChainForge project '{name}' created at {base}")


def _generate_quickstart(provider: str):
    """Print a minimal quickstart script."""
    provider_import = {
        "openai": "from chainforge.providers import OpenAIProvider\nllm = OpenAIProvider()",
        "anthropic": "from chainforge.providers import AnthropicProvider\nllm = AnthropicProvider()",
        "google": "from chainforge.providers import GoogleProvider\nllm = GoogleProvider()",
    }
    print(f'''"""ChainForge Quickstart — {provider}"""
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
''')


if __name__ == "__main__":
    main()
