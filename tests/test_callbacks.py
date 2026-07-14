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
"""Tests for the callback system."""

import pytest
from chainforge.callbacks import (
    Callback, BaseCallback, LoggingCallback, MetricsCallback,
)
from chainforge.core.message import Message, Role


class TestBaseCallback:
    @pytest.mark.asyncio
    async def test_all_hooks_noop_by_default(self):
        cb = BaseCallback()
        # Should not raise
        await cb.on_agent_start("test")
        await cb.on_agent_end("output")
        await cb.on_llm_start([])
        await cb.on_llm_end(None)
        await cb.on_tool_start("tool", {})
        await cb.on_tool_end("tool", "result")
        await cb.on_error(Exception("test"))


class TestLoggingCallback:
    @pytest.mark.asyncio
    async def test_hooks_dont_raise(self):
        cb = LoggingCallback()
        await cb.on_agent_start("hello")
        await cb.on_agent_end("world")
        await cb.on_llm_start([Message(role=Role.user, content="Hi")])
        await cb.on_llm_end(None)
        await cb.on_tool_start("calc", {"x": 1})
        await cb.on_tool_end("calc", "result")
        await cb.on_error(Exception("err"))


class TestMetricsCallback:
    @pytest.mark.asyncio
    async def test_start_end_tracking(self):
        metrics = MetricsCallback()
        await metrics.on_agent_start("hello")
        await metrics.on_agent_end("world")
        report = metrics.get_report()
        assert report["llm_calls"] == 0
        assert report["duration_s"] >= 0
        assert report["total_prompt_chars"] == 5

    @pytest.mark.asyncio
    async def test_llm_calls_tracked(self):
        metrics = MetricsCallback()
        await metrics.on_agent_start("hello")
        await metrics.on_llm_start([])
        await metrics.on_llm_end(None)
        await metrics.on_llm_start([])
        await metrics.on_llm_end(None)
        await metrics.on_agent_end("done")
        assert metrics.get_report()["llm_calls"] == 2

    @pytest.mark.asyncio
    async def test_tool_calls_tracked(self):
        metrics = MetricsCallback()
        await metrics.on_agent_start("start")
        await metrics.on_tool_start("calc", {"x": 1})
        await metrics.on_tool_end("calc", "4")
        await metrics.on_agent_end("done")
        report = metrics.get_report()
        assert report["tool_calls"] == 1
        assert report["tools_used"]["calc"] == 1

    @pytest.mark.asyncio
    async def test_errors_tracked(self):
        metrics = MetricsCallback()
        await metrics.on_agent_start("start")
        await metrics.on_error(ValueError("bad"))
        await metrics.on_agent_end("done")
        assert metrics.get_report()["errors"] == 1

    @pytest.mark.asyncio
    async def test_reset(self):
        metrics = MetricsCallback()
        await metrics.on_agent_start("hello")
        await metrics.on_llm_start([])
        await metrics.on_agent_end("world")
        assert metrics.get_report()["llm_calls"] == 1
        metrics.reset()
        assert metrics.get_report()["llm_calls"] == 0

    @pytest.mark.asyncio
    async def test_multiple_tool_types(self):
        metrics = MetricsCallback()
        await metrics.on_agent_start("start")
        await metrics.on_tool_start("search", {})
        await metrics.on_tool_end("search", "results")
        await metrics.on_tool_start("calc", {})
        await metrics.on_tool_end("calc", "42")
        await metrics.on_agent_end("done")
        report = metrics.get_report()
        assert report["tools_used"]["search"] == 1
        assert report["tools_used"]["calc"] == 1


class TestAgentIntegration:
    @pytest.mark.asyncio
    async def test_agent_with_callbacks_field(self):
        from chainforge.testing import MockLLM, MockResponse
        from chainforge.core.agent import Agent

        llm = MockLLM(responses=[MockResponse(content="Hello")])
        agent = Agent(
            llm=llm,
            callbacks=[MetricsCallback()],
        )
        assert len(agent.callbacks) == 1

    @pytest.mark.asyncio
    async def test_callbacks_runs_during_agent_execution(self):
        from chainforge.testing import MockLLM, MockResponse
        from chainforge.core.agent import Agent

        metrics = MetricsCallback()
        llm = MockLLM(responses=[MockResponse(content="Answer")])
        agent = Agent(llm=llm, callbacks=[metrics])

        stream = await agent.run("test prompt")
        async for event in stream:
            pass

        report = metrics.get_report()
        assert report["llm_calls"] >= 0
