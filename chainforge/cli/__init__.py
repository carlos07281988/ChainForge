"""ChainForge CLI — scaffold, skill, serve, and more."""

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
    i = sub.add_parser("init", help="Scaffold a new ChainForge project")
    i.add_argument("name", help="Project name")
    i.add_argument("--dir", default=".", help="Target directory")

    # chainforge quickstart
    q = sub.add_parser("quickstart", help="Generate a minimal agent script")
    q.add_argument("--provider", default="openai", choices=["openai", "anthropic", "google"])

    # chainforge skill
    sk = sub.add_parser("skill", help="Manage skills")
    sk_sub = sk.add_subparsers(dest="skill_command")
    sk_sub.add_parser("list", help="List available skills")
    sa = sk_sub.add_parser("add", help="Register a skill")
    sa.add_argument("path", help="Path to SKILL.md or skill directory")
    si = sk_sub.add_parser("info", help="Show skill details")
    si.add_argument("name", help="Skill name")

    # chainforge serve
    sv = sub.add_parser("serve", help="Start the HTTP API server")
    sv.add_argument("--host", default="0.0.0.0", help="Bind host")
    sv.add_argument("--port", type=int, default=8000, help="Bind port")
    sv.add_argument("--reload", action="store_true", help="Auto-reload on code changes")
    sv.add_argument("--agent", action="append", dest="agent_specs",
                    help="Register an agent: name=ClassName:param=val,...")

    # chainforge eval
    ev = sub.add_parser("eval", help="Run evaluation tests")
    ev.add_argument("agent_id", help="Registered agent ID")
    ev.add_argument("--cases", nargs="*", default=None, help="Specific test case names to run")
    ev.add_argument("--suite", default=None, help="Eval suite JSON file or inline JSON")
    ev.add_argument("--format", default="text", choices=["text", "json", "markdown", "html"], help="Report format")
    ev.add_argument("--output", default=None, help="Save report to file")

    # chainforge run (quick CLI run)
    r = sub.add_parser("run", help="Run an agent directly (requires registered agent)")
    r.add_argument("agent_id", help="Registered agent ID or inline spec")
    r.add_argument("prompt", nargs="*", help="Prompt text")

    args = parser.parse_args()

    if args.command == "init":
        _scaffold_project(args.name, args.dir)
    elif args.command == "quickstart":
        _generate_quickstart(args.provider)
    elif args.command == "skill":
        _handle_skill(args)
    elif args.command == "serve":
        _handle_serve(args)
    elif args.command == "run":
        _handle_run(args)
    elif args.command == "eval":
        _handle_eval(args)
    else:
        parser.print_help()


def _handle_skill(args):
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
        from chainforge.skills.loader import load_skill_from_file
        if os.path.isfile(args.path) and args.path.endswith("SKILL.md"):
            skill = load_skill_from_file(args.path)
            registry.register(skill)
            print(f"✅ Registered skill: {skill.name}")
        elif os.path.isdir(args.path):
            skills = registry.load_dir(args.path)
            print(f"✅ Registered {len(skills)} skill(s)")
        else:
            print(f"❌ No SKILL.md at {args.path}")
    elif args.skill_command == "info":
        from chainforge.skills.loader import load_skill_from_file
        found = None
        if args.path and (args.path.endswith("SKILL.md") or "/" in args.path):
            try:
                found = load_skill_from_file(args.path)
            except FileNotFoundError:
                pass
        if found is None:
            registry.load_dir(".")
            found = registry.get(args.name)
        if found:
            print(f"Name:        {found.name}")
            print(f"Description: {found.description}")
            print(f"Version:     {found.spec.version}")
            print(f"Tags:        {', '.join(found.spec.tags) if found.spec.tags else '(none)'}")
            print(f"\nInstructions:\n{found.instructions[:500]}")
        else:
            print(f"❌ Skill not found: {args.name}")


def _handle_serve(args):
    """Start the HTTP server with optionally registered agents."""
    from chainforge.server import register_agent, run_server

    if args.agent_specs:
        for spec in args.agent_specs:
            _parse_and_register(spec)

    run_server(host=args.host, port=args.port, reload=args.reload)


def _parse_and_register(spec: str):
    """Parse 'name=AgentClass:key=val,...' and register."""
    try:
        name_part, _, config_part = spec.partition("=")
        name = name_part.strip()
        cls_name, _, params_str = config_part.partition(":")
        cls_name = cls_name.strip()
        from chainforge import Agent
        from chainforge.providers import OpenAIProvider
        cls_map = {"Agent": Agent, "agent": Agent}
        cls = cls_map.get(cls_name, Agent)
        llm = OpenAIProvider()
        agent = cls(llm=llm)
        register_agent(name, agent, f"CLI-registered {cls_name}")
        print(f"  Registered agent '{name}' ({cls_name})")
    except Exception as e:
        print(f"  ⚠️  Failed to register '{spec}': {e}")



def _handle_eval(args):
    """Run evaluation tests against a registered agent."""
    import asyncio
    import json
    from pathlib import Path

    from chainforge.server import _agent_registry as registry, _get_agent
    from chainforge.eval.case import EvalCase
    from chainforge.eval.suite import EvalSuite
    from chainforge.eval.runner import EvalRunner
    from chainforge.eval.report import format_report

    if args.agent_id not in registry:
        print(f"❌ Agent '{args.agent_id}' not found. Registered: {list(registry.keys())}")
        return

    agent, _ = _get_agent(args.agent_id)

    # Load suite from file or use default
    if args.suite:
        try:
            if Path(args.suite).exists():
                suite = EvalSuite.from_json(args.suite)
            else:
                suite = EvalSuite.from_json_str(args.suite)
        except Exception as e:
            print(f"❌ Failed to load suite: {e}")
            return
    else:
        from chainforge.eval.case import sample_cases
        suite = EvalSuite(name="cli-run", description="CLI evaluation", cases=sample_cases())

    # Filter cases
    if args.cases:
        suite = suite.filter(names=args.cases)

    if len(suite) == 0:
        print("❌ No matching test cases found.")
        return

    print(f"🧪 Evaluating agent '{args.agent_id}' with {len(suite)} test case(s)...")
    runner = EvalRunner(agent, suite, name=args.agent_id)

    result = asyncio.run(runner.run_all())

    # Output report
    report = format_report(result, fmt=args.format, path=args.output)
    print(report)

    if result.pass_rate == 1.0:
        print(f"\n✅ All {result.total_cases} tests passed!")
    else:
        print(f"\n⚠️  {result.total_passed}/{result.total_cases} passed ({round(result.pass_rate * 100, 1)}%)")


def _handle_run(args):
    prompt = " ".join(args.prompt) if args.prompt else "Hello"
    from chainforge.server import register_agent as reg, _agent_registry as registry
    from chainforge import Agent
    from chainforge.providers import OpenAIProvider

    if args.agent_id not in registry:
        # Auto-register a default agent
        reg(args.agent_id, Agent(llm=OpenAIProvider()), "CLI-run agent")

    import asyncio
    from chainforge.server import _get_agent

    agent, _ = _get_agent(args.agent_id)

    async def _run():
        stream = await agent.run(prompt)
        async for event in stream:
            if event.type == "text" and event.content:
                print(event.content, end="", flush=True)
        print()

    asyncio.run(_run())


# ── scaffold / quickstart / init ─────────────────────────────────────────────

def _scaffold_project(name: str, target_dir: str):
    from pathlib import Path
    base = Path(target_dir) / name
    if base.exists():
        print(f"❌ Directory '{base}' already exists.")
        sys.exit(1)
    for d in ["", "agents", "tools", "skills", "workflows", "tests"]:
        p = base / d
        p.mkdir(parents=True)
        (p / "__init__.py").write_text("")
    (base / "config.py").write_text(
        '"""ChainForge config."""\nfrom chainforge import Agent\nfrom chainforge.providers import OpenAIProvider\n'
        'llm = OpenAIProvider(model="gpt-4o")\nAGENT_DEFAULTS = {"llm": llm, "max_iterations": 10}\n'
    )
    (base / "main.py").write_text(
        '"""Main agent."""\nimport asyncio\nfrom chainforge import Agent, tool\nfrom chainforge.providers import OpenAIProvider\n\n'
        '@tool\ndef greet(name: str) -> str:\n    """Greet someone."""\n    return f"Hello, {name}!"\n\n'
        'async def main():\n    agent = Agent(llm=OpenAIProvider(), tools=[greet], system_prompt="You are friendly.")\n'
        '    async for e in await agent.run("Say hello to ChainForge!"):\n        if e.type == "text":\n            print(e.content, end="", flush=True)\n\n'
        'if __name__ == "__main__":\n    asyncio.run(main())\n'
    )
    (base / ".env.example").write_text("OPENAI_API_KEY=\nANTHROPIC_API_KEY=\nGOOGLE_API_KEY=\n")
    print(f"✅ ChainForge project '{name}' created at {base}")


def _generate_quickstart(provider: str):
    imports = {
        "openai": "from chainforge.providers import OpenAIProvider\nllm = OpenAIProvider()",
        "anthropic": "from chainforge.providers import AnthropicProvider\nllm = AnthropicProvider()",
        "google": "from chainforge.providers import GoogleProvider\nllm = GoogleProvider()",
    }
    print(f'"""ChainForge Quickstart — {provider}"""\n'
          'import asyncio\nfrom chainforge import Agent, tool\n\n'
          '@tool\ndef get_weather(city: str) -> str:\n    """Get weather."""\n    return f"Weather in {city}: sunny, 25°C"\n\n'
          'async def main():\n    {imports[provider]}\n'
          '    agent = Agent(llm=llm, tools=[get_weather])\n'
          '    async for e in await agent.run("Weather in Beijing?"):\n        if e.type == "text":\n            print(e.content, end="", flush=True)\n\n'
          'asyncio.run(main())\n')


if __name__ == "__main__":
    main()
