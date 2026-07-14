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
"""Tests for PlanAndExecute, Reflection, SelfAsk agents."""

import pytest
from chainforge.core.agent import Agent


class FakeLLM:
    """A fake LLM that returns canned responses for testing agent patterns."""
    model = "fake"

    def __init__(self, responses=None):
        self.responses = responses or {}
        self.call_count = 0

    async def generate(self, messages, tools=None, **kwargs):
        from chainforge.core.llm import LLMResponse
        self.call_count += 1
        last = messages[-1].content or "" if messages else ""

        # Check for specific patterns in the request
        if "plan" in last.lower() or "create a step" in last.lower():
            return LLMResponse(content='{"thought": "Planning", "steps": [{"step": 1, "description": "Step one"}, {"step": 2, "description": "Step two"}]}')
        if "critique" in last.lower():
            return LLMResponse(content="The answer is good but could include more details about X.")
        if "improve" in last.lower() or "improved version" in last.lower():
            return LLMResponse(content="This is an improved version with more details.")
        if "sub_questions" in last.lower() or "sub-question" in last.lower():
            return LLMResponse(content='{"sub_questions": ["What is X?", "How does Y work?"]}')
        if "synthesize" in last.lower() or "final answer" in last.lower():
            return LLMResponse(content="Final synthesized answer.")
        # Check response model
        if last.startswith("Answer:"):
            return LLMResponse(content=f"Answer to: {last[:100]}")
        if last.startswith("Execute:"):
            return LLMResponse(content=f"Executed: {last[:100]}")
        return LLMResponse(content="Test response")

    async def stream_generate(self, messages, tools=None, **kwargs):
        yield "Test response"


class TestPlanAndExecute:
    @pytest.mark.asyncio
    async def test_basic_flow(self):
        from chainforge.agents.plan_execute import PlanAndExecute
        agent = PlanAndExecute(llm=FakeLLM(), tools=[])
        stream = await agent.run("Test task")
        events = await stream.collect()
        assert any(e.type.value == "done" for e in events)
        assert any(e.data.get("state") == "planning" for e in events if e.type.value == "state")
        assert any(e.data.get("state") == "executing" for e in events if e.type.value == "state")

    @pytest.mark.asyncio
    async def test_state_transitions(self):
        from chainforge.agents.plan_execute import PlanAndExecute
        agent = PlanAndExecute(llm=FakeLLM(), tools=[])
        stream = await agent.run("Task")
        events = await stream.collect()
        states = [e.data.get("state") for e in events if e.type.value == "state"]
        assert "planning" in states
        assert "executing" in states
        assert "synthesizing" in states
        assert "done" in states


class TestReflection:
    @pytest.mark.asyncio
    async def test_basic_generation(self):
        from chainforge.agents.reflection import Reflection
        agent = Reflection(llm=FakeLLM(), tools=[], reflection_rounds=0)
        stream = await agent.run("Test")
        events = await stream.collect()
        assert any(e.type.value == "done" for e in events)

    @pytest.mark.asyncio
    async def test_reflection_cycle(self):
        from chainforge.agents.reflection import Reflection
        agent = Reflection(llm=FakeLLM(), tools=[], reflection_rounds=1)
        stream = await agent.run("Test with reflection")
        events = await stream.collect()
        states = [e.data.get("state") for e in events if e.type.value == "state"]
        assert "generating" in states
        assert "critiquing" in states
        assert "improving" in states

    @pytest.mark.asyncio
    async def test_multiple_rounds(self):
        from chainforge.agents.reflection import Reflection
        agent = Reflection(llm=FakeLLM(), tools=[], reflection_rounds=2)
        stream = await agent.run("Multiple rounds")
        events = await stream.collect()
        states = [e for e in events if e.type.value == "state"]
        critiquing = [s for s in states if s.data.get("state") == "critiquing"]
        assert len(critiquing) == 2


class TestSelfAsk:
    @pytest.mark.asyncio
    async def test_basic_flow(self):
        from chainforge.agents.self_ask import SelfAsk
        agent = SelfAsk(llm=FakeLLM(), tools=[])
        stream = await agent.run("What is AI?")
        events = await stream.collect()
        assert any(e.type.value == "done" for e in events)

    @pytest.mark.asyncio
    async def test_state_transitions(self):
        from chainforge.agents.self_ask import SelfAsk
        agent = SelfAsk(llm=FakeLLM(), tools=[])
        stream = await agent.run("Question?")
        events = await stream.collect()
        states = [e.data.get("state") for e in events if e.type.value == "state"]
        assert "decomposing" in states
        assert "answering" in states
        assert "synthesizing" in states

    @pytest.mark.asyncio
    async def test_sub_questions_emitted(self):
        from chainforge.agents.self_ask import SelfAsk
        agent = SelfAsk(llm=FakeLLM(), tools=[])
        stream = await agent.run("Big question?")
        events = await stream.collect()
        text_events = [e for e in events if e.type.value == "text"]
        has_sub_questions = any("[Sub-questions]" in (e.content or "") for e in text_events)
        assert has_sub_questions


class TestAgentImports:
    def test_all_agents_importable(self):
        from chainforge.agents import ReActAgent, ToolAgent, PlanAndExecute, Reflection, SelfAsk
        assert ReActAgent is not None
        assert ToolAgent is not None
        assert PlanAndExecute is not None
        assert Reflection is not None
        assert SelfAsk is not None
