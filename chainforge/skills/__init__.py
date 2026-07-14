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
