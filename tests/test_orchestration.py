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
"""Tests for orchestration module."""

import pytest
from chainforge.orchestration import Swarm, Supervisor


class TestSwarm:
    def test_swarm_creation(self):
        swarm = Swarm(agents=[], name="test")
        assert swarm.name == "test"
        assert len(swarm.agents) == 0

    def test_swarm_with_agents(self):
        from chainforge.core.agent import Agent

        class FakeLLM:
            model = "fake"
            async def generate(self, messages, tools=None, **kwargs):
                from chainforge.core.llm import LLMResponse
                return LLMResponse(content="test response")
            async def stream_generate(self, messages, tools=None, **kwargs):
                yield "test"

        agents = [
            Agent(llm=FakeLLM()),
            Agent(llm=FakeLLM()),
        ]
        swarm = Swarm(agents=agents)
        assert len(swarm.agents) == 2

    @pytest.mark.asyncio
    async def test_swarm_async_run(self):
        from chainforge.core.agent import Agent

        class FakeLLM:
            model = "fake"
            async def generate(self, messages, tools=None, **kwargs):
                from chainforge.core.llm import LLMResponse
                return LLMResponse(content="test")
            async def stream_generate(self, messages, tools=None, **kwargs):
                yield "test"

        swarm = Swarm(agents=[Agent(llm=FakeLLM())], name="test")
        stream = await swarm.run("hello")
        events = await stream.collect()
        assert any(e.type.value == "done" for e in events)


class TestSupervisor:
    def test_supervisor_creation(self):
        from chainforge.core.agent import Agent

        class FakeLLM:
            model = "fake"
            async def generate(self, messages, tools=None, **kwargs):
                from chainforge.core.llm import LLMResponse
                return LLMResponse(content="I'll handle this directly")
            async def stream_generate(self, messages, tools=None, **kwargs):
                yield "I'll handle this directly"

        sup = Agent(llm=FakeLLM())
        supervisor = Supervisor(supervisor_agent=sup)
        assert supervisor.max_delegations == 5

    def test_supervisor_with_workers(self):
        from chainforge.core.agent import Agent

        class FakeLLM:
            model = "fake"
            async def generate(self, messages, tools=None, **kwargs):
                from chainforge.core.llm import LLMResponse
                return LLMResponse(content="ok")
            async def stream_generate(self, messages, tools=None, **kwargs):
                yield "ok"

        sup = Agent(llm=FakeLLM())
        worker = Agent(llm=FakeLLM())
        supervisor = Supervisor(
            supervisor_agent=sup,
            workers={"search": worker},
        )
        assert "search" in supervisor.workers
