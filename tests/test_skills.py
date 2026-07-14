# Copyright 2026 ChainForge Contributors
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
"""Tests for the skill system."""

import tempfile
from pathlib import Path

import pytest

from chainforge.skills import Skill, SkillRegistry
from chainforge.skills.loader import load_skill_from_file, load_skills_from_directory
from chainforge.core.agent import Agent


class TestSkillModel:
    def test_skill_flat_creation(self):
        skill = Skill(name="test-skill", description="A test skill",
                      instructions="Do something useful")
        assert skill.name == "test-skill"
        assert skill.description == "A test skill"
        assert skill.instructions == "Do something useful"

    def test_skill_spec_creation(self):
        from chainforge.skills.base import SkillSpec
        spec = SkillSpec(name="test", description="desc", tags=["ai", "test"])
        skill = Skill(spec=spec, instructions="Do X")
        assert skill.name == "test"
        assert "ai" in skill.spec.tags

    def test_to_system_block(self):
        skill = Skill(name="helper", description="Helps", instructions="Be helpful")
        block = skill.to_system_block()
        assert "=== Skill: helper ===" in block
        assert "Be helpful" in block

    def test_to_tool_spec(self):
        skill = Skill(name="search", description="Search tool")
        spec = skill.to_tool_spec()
        assert spec.name == "search"
        assert "query" in spec.parameters["properties"]

    def test_to_tool(self):
        skill = Skill(name="echo", description="Echo skill", instructions="Echo back")
        tool = skill.to_tool()
        assert tool.spec.name == "echo"

    def test_skill_with_tools(self):
        from chainforge.core.tool import tool
        @tool
        def my_tool(x: str) -> str:
            """A tool."""
            return x

        skill = Skill(name="with-tools", description="Has tools", tools=[my_tool])
        assert len(skill.tools) == 1


class TestSkillLoader:
    def test_load_from_skill_md(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "my-skill"
            skill_dir.mkdir()
            skill_file = skill_dir / "SKILL.md"
            skill_file.write_text("""---
name: test-skill
description: A test skill
tags: [test, demo]
---

## Instructions

Be helpful and kind.
""")
            skill = load_skill_from_file(str(skill_file))
            assert skill.name == "test-skill"
            assert skill.description == "A test skill"
            assert "helpful" in skill.instructions
            assert "demo" in skill.spec.tags

    def test_load_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            s1 = Path(tmp) / "skill-a" / "SKILL.md"
            s1.parent.mkdir()
            s1.write_text("---\nname: skill-a\ndescription: First\n---\n\nInstr A")
            s2 = Path(tmp) / "skill-b" / "SKILL.md"
            s2.parent.mkdir()
            s2.write_text("---\nname: skill-b\ndescription: Second\n---\n\nInstr B")

            skills = load_skills_from_directory(tmp)
            names = {s.name for s in skills}
            assert "skill-a" in names
            assert "skill-b" in names

    def test_load_missing_file(self):
        with pytest.raises(FileNotFoundError):
            load_skill_from_file("/nonexistent/SKILL.md")

    def test_load_without_front_matter(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill_file = Path(tmp) / "SKILL.md"
            skill_file.write_text("Just instructions, no front matter.")
            skill = load_skill_from_file(str(skill_file))
            # Name derived from directory
            assert skill.instructions == "Just instructions, no front matter."


class TestSkillRegistry:
    def test_register_and_get(self):
        registry = SkillRegistry()
        skill = Skill(name="my-skill", description="Test")
        registry.register(skill)
        assert registry.get("my-skill") is skill
        assert registry.count == 1

    def test_unregister(self):
        registry = SkillRegistry()
        registry.register(Skill(name="a", description="A"))
        registry.unregister("a")
        assert registry.get("a") is None

    def test_list(self):
        registry = SkillRegistry()
        registry.register(Skill(name="a", description="A"))
        registry.register(Skill(name="b", description="B"))
        assert len(registry.list()) == 2

    def test_search(self):
        registry = SkillRegistry()
        registry.register(Skill(name="weather", description="Get weather data"))
        registry.register(Skill(name="search", description="Search the web"))
        results = registry.search("weather")
        assert len(results) == 1
        assert results[0].name == "weather"

    def test_find_by_tag(self):
        registry = SkillRegistry()
        from chainforge.skills.base import SkillSpec
        s1 = Skill(spec=SkillSpec(name="a", tags=["demo"]))
        s2 = Skill(spec=SkillSpec(name="b", tags=["prod"]))
        registry.register(s1)
        registry.register(s2)
        assert len(registry.find_by_tag("demo")) == 1
        assert len(registry.find_by_tag("prod")) == 1

    def test_to_tools(self):
        registry = SkillRegistry()
        registry.register(Skill(name="skill-a", description="A"))
        tools = registry.to_tools()
        assert len(tools) == 1

    def test_summarize(self):
        registry = SkillRegistry()
        registry.register(Skill(name="x", description="X"))
        summary = registry.summarize()
        assert len(summary) == 1
        assert summary[0]["name"] == "x"

    def test_clear(self):
        registry = SkillRegistry()
        registry.register(Skill(name="a", description="A"))
        registry.clear()
        assert registry.count == 0

    def test_load_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = Path(tmp) / "test-skill" / "SKILL.md"
            s.parent.mkdir()
            s.write_text("---\nname: test-skill\ndescription: Test\n---\n\nInstructions")
            registry = SkillRegistry()
            registry.load_dir(tmp)
            assert registry.get("test-skill") is not None


class TestAgentSkillIntegration:
    def test_skills_in_agent_creation(self):
        skill = Skill(name="helper", description="A helper skill",
                      instructions="Be helpful")
        class FakeLLM:
            model = "fake"
            async def generate(self, messages, tools=None, **kwargs):
                from chainforge.core.llm import LLMResponse
                return LLMResponse(content="ok")
            async def stream_generate(self, messages, tools=None, **kwargs):
                yield "ok"

        agent = Agent(llm=FakeLLM(), skills=[skill])
        assert len(agent.skills) == 1
        assert agent.skills[0].name == "helper"

    def test_skill_tools_are_collected(self):
        from chainforge.core.tool import tool
        @tool
        def skill_tool(x: str) -> str:
            return x

        skill = Skill(name="with-tools", description="Tools", instructions="Do stuff",
                      tools=[skill_tool])
        class FakeLLM:
            model = "fake"
            async def generate(self, messages, tools=None, **kwargs):
                from chainforge.core.llm import LLMResponse
                return LLMResponse(content="ok")
            async def stream_generate(self, messages, tools=None, **kwargs):
                yield "ok"

        agent = Agent(llm=FakeLLM(), skills=[skill])
        all_tools = agent._all_tools()
        assert any(t.spec.name == "with-tools" for t in all_tools)
        assert any(t.spec.name == "skill_tool" for t in all_tools)

    def test_skill_system_prompt_composition(self):
        skill = Skill(name="translator", description="Translates",
                      instructions="You are a translator. Translate to Chinese.")
        class FakeLLM:
            model = "fake"
            async def generate(self, messages, tools=None, **kwargs):
                from chainforge.core.llm import LLMResponse
                return LLMResponse(content="ok")
            async def stream_generate(self, messages, tools=None, **kwargs):
                yield "ok"

        agent = Agent(llm=FakeLLM(), skills=[skill],
                      system_prompt="You are helpful.")
        composed = agent._build_system_prompt()
        assert "You are helpful" in composed
        assert "=== Skill: translator ===" in composed
        assert "Translate to Chinese" in composed


class TestSkillTool:
    @pytest.mark.asyncio
    async def test_skill_tool_run(self):
        skill = Skill(name="test-skill", description="Test",
                      instructions="Do the thing")
        tool = skill.to_tool()
        result = await tool.run(query="help me")
        assert "test-skill" in result
        assert "Do the thing" in result
        assert "help me" in result
