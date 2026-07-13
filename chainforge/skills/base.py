"""Skill model — a reusable capability bundle."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ConfigDict

from chainforge.core.tool import Tool, ToolSpec


class SkillSpec(BaseModel):
    name: str = Field(description="Unique skill identifier")
    description: str = Field(default="", description="What this skill does")
    version: str = Field(default="1.0.0", description="Semantic version")
    tags: list[str] = Field(default_factory=list, description="Categorization tags")
    requires_tools: list[str] = Field(default_factory=list, description="Tool dependencies")
    requires_mcp: list[str] = Field(default_factory=list, description="MCP server dependencies")


class Skill(BaseModel):
    """A reusable capability that an agent can load and compose."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    spec: SkillSpec = Field(description="Skill metadata")
    instructions: str = Field(default="", description="Core instructions defining the skill")
    tools: list = Field(default_factory=list, description="Optional tools this skill provides")
    system_prompt_append: str | None = Field(default=None, description="Extra text appended to agent's system prompt")

    def __init__(self, **data):
        if "spec" not in data and "name" in data:
            data["spec"] = SkillSpec(
                name=data.pop("name"),
                description=data.pop("description", ""),
                tags=data.pop("tags", []),
            )
        super().__init__(**data)

    @property
    def name(self) -> str:
        return self.spec.name

    @property
    def description(self) -> str:
        return self.spec.description

    def to_system_block(self) -> str:
        lines = [f"=== Skill: {self.name} ==="]
        if self.description:
            lines.append(f"Description: {self.description}")
        if self.instructions:
            lines.append("")
            lines.append(self.instructions)
        if self.system_prompt_append:
            lines.append("")
            lines.append(self.system_prompt_append)
        return "\n".join(lines)

    def to_tool(self) -> "SkillTool":
        return SkillTool(skill=self)

    def to_tool_spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.name,
            description=self.description or f"Skill: {self.name}",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": f"The query or task for the '{self.name}' skill",
                    }
                },
                "required": ["query"],
            },
        )

    @classmethod
    def load(cls, path: str | Path) -> "Skill":
        from chainforge.skills.loader import load_skill_from_file
        return load_skill_from_file(str(path))


class SkillTool:
    """A Tool wrapper that invokes a Skill."""

    def __init__(self, skill: Skill):
        self._skill = skill
        self._spec = skill.to_tool_spec()

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    async def run(self, query: str = "", **kwargs: Any) -> str:
        parts = [f"## Skill: {self._skill.name}"]
        if self._skill.instructions:
            parts.append(self._skill.instructions)
        if query:
            parts.append(f"\n## Query\n{query}")
        return "\n\n".join(parts)

    def __call__(self, query: str = "", **kwargs: Any) -> str:
        from chainforge.core.utils import run_sync
        return run_sync(self.run(query=query, **kwargs))

    def __repr__(self) -> str:
        return f"SkillTool(name={self._skill.name!r})"
