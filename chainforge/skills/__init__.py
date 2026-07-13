"""Skill system — reusable capabilities for ChainForge agents.

Skills are self-contained bundles of instructions (+ optional tools) that
agents can load and compose. Compatible with Codex SKILL.md format.

Usage:
    skill = Skill.load("path/to/SKILL.md")
    agent = Agent(llm=llm, skills=[skill], tools=[...])

    # Or discover skills dynamically:
    registry = SkillRegistry()
    registry.load_dir("./skills")
    for skill in registry.list():
        agent.tools.append(skill.to_tool())
"""

from chainforge.skills.base import Skill, SkillTool, SkillSpec
from chainforge.skills.registry import SkillRegistry

__all__ = ["Skill", "SkillTool", "SkillSpec", "SkillRegistry"]
