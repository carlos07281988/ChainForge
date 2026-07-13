"""Skill registry — discover, register, and query skills.

Acts as a central catalog for skills loaded from files,
directories, or registered programmatically.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from chainforge.skills.base import Skill, SkillSpec
from chainforge.skills.loader import load_skills_from_directory


class SkillRegistry:
    """A catalog of skills that agents can discover and load.

    Usage:
        registry = SkillRegistry()
        registry.load_dir("./skills")
        registry.register(my_skill)

        for name, skill in registry.list():
            print(f"  {name}: {skill.description}")
    """

    def __init__(self):
        self._skills: dict[str, Skill] = {}

    # ── Registration ──────────────────────────────────────────────────────

    def register(self, skill: Skill) -> None:
        """Register a skill by name."""
        self._skills[skill.name] = skill

    def unregister(self, name: str) -> None:
        """Remove a skill from the registry."""
        self._skills.pop(name, None)

    # ── Loading ───────────────────────────────────────────────────────────

    def load_dir(self, path: str | Path) -> list[Skill]:
        """Load all SKILL.md files from a directory tree into the registry."""
        skills = load_skills_from_directory(str(path))
        for s in skills:
            self.register(s)
        return skills

    # ── Querying ──────────────────────────────────────────────────────────

    def get(self, name: str) -> Skill | None:
        """Look up a skill by name."""
        return self._skills.get(name)

    def list(self) -> list[Skill]:
        """List all registered skills."""
        return list(self._skills.values())

    def find_by_tag(self, tag: str) -> list[Skill]:
        """Find skills that have a specific tag."""
        return [s for s in self._skills.values() if tag in s.spec.tags]

    def search(self, query: str) -> list[Skill]:
        """Search skills by name or description (case-insensitive)."""
        q = query.lower()
        return [
            s for s in self._skills.values()
            if q in s.name.lower() or q in s.description.lower()
        ]

    def clear(self) -> None:
        """Remove all registered skills."""
        self._skills.clear()

    @property
    def count(self) -> int:
        return len(self._skills)

    def to_tools(self) -> list:
        """Convert all registered skills to a list of SkillTool objects."""
        return [s.to_tool() for s in self._skills.values()]

    def summarize(self) -> list[dict[str, Any]]:
        """Return a summary of all skills (for LLM context)."""
        return [
            {"name": s.name, "description": s.description, "tags": s.spec.tags}
            for s in self._skills.values()
        ]
