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
"""Tests for reasoning strategies."""

import pytest
from chainforge.reasoning import (
    ReasoningStrategy,
    ChainOfThought,
    ReasoningSteps,
    SelfReflection,
    Verification,
)
from chainforge.core.message import Message, Role


class TestReasoningStrategy:
    @pytest.mark.asyncio
    async def test_base_hooks_return_values(self):
        s = ReasoningStrategy()
        msgs = [Message(role=Role.user, content="Hi")]
        result_msgs, ctx = await s.before_llm(msgs, {})
        assert len(result_msgs) == 1

    @pytest.mark.asyncio
    async def test_should_stop_default_false(self):
        s = ReasoningStrategy()
        assert await s.should_stop([]) is False


class TestChainOfThought:
    @pytest.mark.asyncio
    async def test_injects_cot_prompt(self):
        cot = ChainOfThought()
        msgs = [Message(role=Role.user, content="Solve this")]
        result_msgs, ctx = await cot.before_llm(msgs)
        assert len(result_msgs) == 2
        assert "step by step" in result_msgs[1].content.lower()

    @pytest.mark.asyncio
    async def test_does_not_duplicate_cot(self):
        cot = ChainOfThought()
        msgs = [Message(role=Role.system, content="Think step by step")]
        result_msgs, ctx = await cot.before_llm(msgs)
        assert len(result_msgs) == 1  # No duplicate

    @pytest.mark.asyncio
    async def test_custom_prompt(self):
        cot = ChainOfThought(prompt="Work through this carefully.")
        msgs = [Message(role=Role.user, content="Hi")]
        result_msgs, ctx = await cot.before_llm(msgs)
        assert "carefully" in result_msgs[1].content


class TestReasoningSteps:
    @pytest.mark.asyncio
    async def test_injects_plan_on_first_iteration(self):
        rs = ReasoningSteps(max_steps=3)
        msgs = [Message(role=Role.user, content="Tell me about Python")]
        result_msgs, ctx = await rs.before_llm(msgs, {"iteration": 0})
        assert len(result_msgs) == 2
        assert "steps" in result_msgs[1].content.lower()

    @pytest.mark.asyncio
    async def test_no_plan_on_subsequent(self):
        rs = ReasoningSteps(max_steps=3)
        msgs = [Message(role=Role.user, content="Hi")]
        result_msgs, ctx = await rs.before_llm(msgs, {"iteration": 2})
        assert len(result_msgs) == 1

    @pytest.mark.asyncio
    async def test_should_stop_after_max(self):
        rs = ReasoningSteps(max_steps=2)
        assert await rs.should_stop([]) is False  # step 1
        assert await rs.should_stop([]) is True   # step 2 (>= max)


class TestSelfReflection:
    @pytest.mark.asyncio
    async def test_does_not_reflect_on_tool_calls(self):
        ref = SelfReflection(max_reflections=2)
        msgs = [Message(role=Role.user, content="Hi")]
        class FakeResponse:
            content = ""
            tool_calls = [{"name": "calc", "args": {}}]
        resp, result_msgs, ctx = await ref.after_llm(FakeResponse(), msgs, {})
        assert ref._reflection_count == 0

    @pytest.mark.asyncio
    async def test_should_stop_after_max(self):
        ref = SelfReflection(max_reflections=2)
        ref._reflection_count = 2
        assert await ref.should_stop([]) is True


class TestVerification:
    @pytest.mark.asyncio
    async def test_does_not_verify_tool_calls(self):
        v = Verification()
        msgs = [Message(role=Role.user, content="Hi")]
        class FakeResponse:
            content = ""
            tool_calls = [{"name": "calc", "args": {}}]
        resp, result_msgs, ctx = await v.after_llm(FakeResponse(), msgs, {})
        assert v._verified is False

    @pytest.mark.asyncio
    async def test_should_stop_after_verify(self):
        v = Verification()
        v._verified = True
        assert await v.should_stop([]) is True


class TestAgentIntegration:
    @pytest.mark.asyncio
    async def test_agent_with_reasoning_field(self):
        from chainforge.testing import MockLLM, MockResponse
        from chainforge.core.agent import Agent

        llm = MockLLM(responses=[MockResponse(content="Simple answer")])
        agent = Agent(
            llm=llm,
            reasoning=[ChainOfThought()],
        )
        assert len(agent.reasoning) == 1
        assert isinstance(agent.reasoning[0], ChainOfThought)

    @pytest.mark.asyncio
    async def test_reasoning_runs_in_loop(self):
        from chainforge.testing import MockLLM, MockResponse
        from chainforge.core.agent import Agent

        llm = MockLLM(responses=[MockResponse(content="Final answer")])
        agent = Agent(
            llm=llm,
            reasoning=[ChainOfThought()],
        )
        stream = await agent.run("Test")
        texts = []
        async for event in stream:
            if hasattr(event, "type") and event.type == "text" and event.content:
                texts.append(event.content)
        assert any("Final" in t for t in texts)
