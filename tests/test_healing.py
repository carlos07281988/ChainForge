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
"""Tests for Self-Healing Agents."""

import asyncio

import pytest

from chainforge.core.healing import HealingPolicy, SelfHealingWrapper, ErrorCategory, classify_error
from chainforge.core.tool import FunctionTool, ToolSpec


# ── Fixtures ────────────────────────────────────────────────────────────────


def _make_tool(name: str, fn, description: str = ""):
    return FunctionTool(fn, name=name, description=description)


class _FakeLLM:
    model = "test"
    capabilities = set()

    async def generate(self, messages, **kwargs):
        from chainforge.core.llm import LLMResponse
        return LLMResponse(content="Done", tool_calls=[])


# ── Test Error Classification ───────────────────────────────────────────────


class TestErrorClassification:
    def test_tool_error(self):
        assert classify_error(Exception("broke")) == "tool_error"
        assert classify_error(ValueError("bad value")) == "tool_error"

    def test_timeout(self):
        assert classify_error(Exception("timeout occurred")) == "timeout"
        assert classify_error(Exception("timeout occurred")) == "timeout"

    def test_content_error(self):
        assert classify_error("Error: not found") == "content_error"
        assert classify_error("Error: permission denied") == "content_error"

    def test_llm_refusal(self):
        assert classify_error("I cannot do that") == "llm_refusal"
        assert classify_error("Sorry, I cannot help") == "llm_refusal"
        assert classify_error("I refuse to answer") == "llm_refusal"
        assert classify_error("I'm sorry, I can't") == "llm_refusal"

    def test_normal_message(self):
        assert classify_error("normal result") == "tool_error"

    def test_error_category_values(self):
        assert ErrorCategory.TOOL_ERROR == "tool_error"
        assert ErrorCategory.CONTENT_ERROR == "content_error"
        assert ErrorCategory.TIMEOUT == "timeout"
        assert ErrorCategory.LLM_REFUSAL == "llm_refusal"


# ── Test HealingPolicy ──────────────────────────────────────────────────────


class TestHealingPolicy:
    def test_default_policy(self):
        p = HealingPolicy()
        assert p.max_retries == 2
        assert p.retry_delay == 0.5
        assert p.retry_backoff == 1.5
        assert p.fallback_tools == {}
        assert p.track_failures is True
        assert p.auto_escalate is True

    def test_custom_policy(self):
        p = HealingPolicy(
            max_retries=5,
            retry_delay=1.0,
            fallback_tools={"search": ["fetch"]},
            track_failures=False,
            auto_escalate=False,
        )
        assert p.max_retries == 5
        assert p.retry_delay == 1.0
        assert p.fallback_tools == {"search": ["fetch"]}
        assert p.track_failures is False
        assert p.auto_escalate is False


# ── Test SelfHealingWrapper — Creation ──────────────────────────────────────


class TestSelfHealingWrapperCreation:
    def test_create_with_default_policy(self):
        from chainforge.core.agent import Agent
        from chainforge.providers import OpenAIProvider
        agent = Agent(llm=OpenAIProvider(model="gpt-4o"))
        wrapper = SelfHealingWrapper(agent)
        assert wrapper.agent is agent
        assert wrapper._policy.max_retries == 2

    def test_create_with_custom_policy(self):
        from chainforge.core.agent import Agent
        from chainforge.providers import OpenAIProvider
        policy = HealingPolicy(max_retries=5)
        wrapper = SelfHealingWrapper(Agent(llm=OpenAIProvider(model="gpt-4o")), policy=policy)
        assert wrapper._policy.max_retries == 5

    def test_agent_property(self):
        from chainforge.core.agent import Agent
        from chainforge.providers import OpenAIProvider
        agent = Agent(llm=OpenAIProvider(model="gpt-4o"))
        wrapper = SelfHealingWrapper(agent)
        assert wrapper.agent is agent

    def test_reset_stats(self):
        from chainforge.core.agent import Agent
        from chainforge.providers import OpenAIProvider
        wrapper = SelfHealingWrapper(Agent(llm=OpenAIProvider(model="gpt-4o")))
        wrapper._total_failures = 42
        wrapper.reset_stats()
        assert wrapper._total_failures == 0


# ── Test SelfHealingWrapper — Stats ─────────────────────────────────────────


class TestHealingStats:
    def test_empty_stats(self):
        from chainforge.core.agent import Agent
        from chainforge.providers import OpenAIProvider
        wrapper = SelfHealingWrapper(Agent(llm=OpenAIProvider(model="gpt-4o")))
        stats = wrapper.stats()
        assert stats["total_calls"] == 0
        assert stats["successes"] == 0
        assert stats["failures"] == 0
        assert stats["healed"] == 0
        assert stats["heal_rate"] == 1.0
        assert stats["per_tool"] == {}

    def test_stats_with_data(self):
        from chainforge.core.agent import Agent
        from chainforge.providers import OpenAIProvider
        wrapper = SelfHealingWrapper(Agent(llm=OpenAIProvider(model="gpt-4o")))
        wrapper._success_counts["search"] = 10
        wrapper._failure_counts["search"] = 2
        wrapper._total_failures = 2
        wrapper._healed_count = 1
        stats = wrapper.stats()
        assert stats["total_calls"] == 12
        assert stats["successes"] == 10
        assert stats["failures"] == 2
        assert stats["healed"] == 1
        assert stats["per_tool"]["search"]["calls"] == 12
        from pytest import approx
        assert stats["per_tool"]["search"]["success_rate"] == approx(10 / 12, rel=1e-3)


# ── Test SelfHealingWrapper — Tool Wrapping ─────────────────────────────────


class TestToolWrapping:
    def test_successful_tool_passthrough(self):
        """A tool that succeeds should work normally."""
        from chainforge.core.agent import Agent
        from chainforge.providers import OpenAIProvider

        async def success_tool_fn(name: str = "") -> str:
            return f"Hello {name}"

        success_tool = _make_tool("greet", success_tool_fn)
        agent = Agent(llm=OpenAIProvider(model="gpt-4o"), tools=[success_tool])

        wrapper = SelfHealingWrapper(agent)
        wrapped = wrapper._wrap_tool(success_tool)

        result = asyncio.run(wrapped.run(name="World"))
        assert result == "Hello World"

    def test_retry_on_failure(self):
        """A tool that fails once should be retried."""
        from chainforge.core.agent import Agent
        from chainforge.providers import OpenAIProvider

        call_count = [0]

        async def flaky_tool_fn() -> str:
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("First attempt failed")
            return "Success on retry"

        flaky_tool = _make_tool("flaky", flaky_tool_fn)
        agent = Agent(llm=OpenAIProvider(model="gpt-4o"), tools=[flaky_tool])

        wrapper = SelfHealingWrapper(
            agent,
            HealingPolicy(max_retries=2, retry_delay=0.01),
        )
        wrapped = wrapper._wrap_tool(flaky_tool)

        result = asyncio.run(wrapped.run())
        assert result == "Success on retry"
        assert call_count[0] == 2

    def test_fallback_tool(self):
        """If primary tool fails, fallback tool should be used."""
        from chainforge.core.agent import Agent
        from chainforge.providers import OpenAIProvider

        async def primary_fn() -> str:
            raise RuntimeError("Primary failed")

        async def fallback_fn() -> str:
            return "Fallback result"

        primary = _make_tool("primary", primary_fn)
        fallback = _make_tool("backup", fallback_fn)

        agent = Agent(llm=OpenAIProvider(model="gpt-4o"), tools=[primary, fallback])

        wrapper = SelfHealingWrapper(
            agent,
            HealingPolicy(max_retries=0, fallback_tools={"primary": ["backup"]}),
        )
        wrapper._build_fallback_map(agent._all_tools())
        wrapped = wrapper._wrap_tool(primary)

        result = asyncio.run(wrapped.run())
        assert result == "Fallback result"

    def test_all_failures_escalate(self):
        """If all attempts and fallbacks fail, escalate by returning error string."""
        from chainforge.core.agent import Agent
        from chainforge.providers import OpenAIProvider

        async def failing_fn() -> str:
            raise RuntimeError("Always fails")

        failing_tool = _make_tool("bad", failing_fn)
        agent = Agent(llm=OpenAIProvider(model="gpt-4o"), tools=[failing_tool])

        wrapper = SelfHealingWrapper(
            agent,
            HealingPolicy(max_retries=0, auto_escalate=True),
        )
        wrapped = wrapper._wrap_tool(failing_tool)

        result = asyncio.run(wrapped.run())
        assert "Error:" in result
        assert "bad" in result

    def test_stats_tracked_on_failure(self):
        """Failures should be tracked in stats."""
        from chainforge.core.agent import Agent
        from chainforge.providers import OpenAIProvider

        async def failing_fn() -> str:
            raise RuntimeError("Fail")

        failing_tool = _make_tool("fail_tool", failing_fn)
        agent = Agent(llm=OpenAIProvider(model="gpt-4o"), tools=[failing_tool])

        wrapper = SelfHealingWrapper(
            agent,
            HealingPolicy(max_retries=0, track_failures=True, auto_escalate=True),
        )
        wrapped = wrapper._wrap_tool(failing_tool)
        asyncio.run(wrapped.run())

        stats = wrapper.stats()
        # At least 1 failure recorded (original tool)
        assert stats["failures"] >= 1
        assert "fail_tool" in stats["per_tool"]

    def test_healed_stats(self):
        """When fallback succeeds, healed count should increment."""
        from chainforge.core.agent import Agent
        from chainforge.providers import OpenAIProvider

        async def primary_fn() -> str:
            raise RuntimeError("Primary failed")

        async def backup_fn() -> str:
            return "Backup OK"

        primary = _make_tool("primary", primary_fn)
        backup = _make_tool("backup", backup_fn)

        agent = Agent(llm=OpenAIProvider(model="gpt-4o"), tools=[primary, backup])

        wrapper = SelfHealingWrapper(
            agent,
            HealingPolicy(max_retries=0, fallback_tools={"primary": ["backup"]}),
        )
        wrapper._build_fallback_map(agent._all_tools())
        wrapped = wrapper._wrap_tool(primary)
        asyncio.run(wrapped.run())

        stats = wrapper.stats()
        assert stats["healed"] == 1
        assert stats["heal_rate"] > 0
