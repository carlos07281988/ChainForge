# Copyright 2024 ChainForge Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Agent templates — scaffold new projects from predefined configurations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

TEMPLATES_DIR = Path(__file__).parent

TEMPLATE_REGISTRY: dict[str, str] = {
    "chat": "General chat assistant",
    "research": "Research agent with web search and code execution",
    "tool-user": "Tool-using agent with Python and shell access",
}


def list_templates() -> list[dict[str, str]]:
    """List available agent templates."""
    return [
        {"name": name, "description": desc}
        for name, desc in TEMPLATE_REGISTRY.items()
    ]


def get_template_path(name: str) -> Path | None:
    """Get the path to a template directory.

    Args:
        name: Template name (chat, research, tool-user).

    Returns:
        Path to template directory, or None if not found.
    """
    template_dir = TEMPLATES_DIR / name
    if template_dir.exists() and template_dir.is_dir():
        return template_dir
    return None


def scaffold_from_template(name: str, target_dir: str | Path, template: str) -> Path:
    """Scaffold a new project from a template.

    Args:
        name: Project name.
        target_dir: Target directory.
        template: Template name.

    Returns:
        Path to the created project directory.
    """
    from chainforge.config.loader import load_agent_config
    from chainforge.config.builder import build_agent_from_config

    target = Path(target_dir) / name
    if target.exists():
        raise FileExistsError(f"Directory '{target}' already exists.")

    template_path = get_template_path(template)
    if template_path is None:
        raise ValueError(f"Template '{template}' not found. Available: {list(TEMPLATE_REGISTRY.keys())}")

    # Copy template files
    config_path = template_path / "agent.yaml"
    if config_path.exists():
        target.mkdir(parents=True)
        target_config = target / "agent.yaml"
        target_config.write_text(config_path.read_text())
        # Replace name placeholder
        content = target_config.read_text()
        content = content.replace("name: " + template + "-assistant", f"name: {name}")
        target_config.write_text(content)
        (target / "__init__.py").write_text("")
        (target / "main.py").write_text(f'"""Agent: {name}"""\nimport asyncio\nfrom chainforge.config.loader import load_agent_config\nfrom chainforge.config.builder import build_agent_from_config\n\nasync def main():\n    config = load_agent_config("agent.yaml")\n    agent = build_agent_from_config(config)\n    stream = await agent.run("Hello!")\n    async for event in stream:\n        if event.type == "text" and event.content:\n            print(event.content, end="", flush=True)\n\nif __name__ == "__main__":\n    asyncio.run(main())\n')

    return target


def get_template_config(template: str) -> dict[str, Any] | None:
    """Load the agent.yaml config from a template."""
    import yaml
    template_path = get_template_path(template)
    if template_path is None:
        return None
    config_file = template_path / "agent.yaml"
    if not config_file.exists():
        return None
    return yaml.safe_load(config_file.read_text())
