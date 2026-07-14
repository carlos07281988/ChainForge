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
"""Tests for AgentTool, AgentChain, AgentHub."""

import pytest


class FakeLLM:
    model = "fake"
    def __init__(self, fixed_response: str = "test output"):
        self.fixed = fixed_response

    async def generate(self, messages, tools=None, **kwargs):
        from chainforge.core.llm import LLMResponse
        return LLMResponse(content=self.fixed)
    async def stream_generate(self, messages, tools=None, **kwargs):
        yield self.fixed


class TestAgentTool:
    @pytest.mark.asyncio
    async def test_wrap_agent(self):
        from chainforge.core.agent import Agent
        from chainforge.agents.agent_tool import AgentTool

        inner = Agent(llm=FakeLLM("hello from inner"))
        tool = AgentTool(inner, name="inner_agent", description="Inner agent tool")
        assert tool.spec.name == "inner_agent"
        assert "task" in tool.spec.parameters["properties"]

    @pytest.mark.asyncio
    async def test_run_agent_tool(self):
        from chainforge.core.agent import Agent
        from chainforge.agents.agent_tool import AgentTool

        inner = Agent(llm=FakeLLM("result from inner"))
        tool = AgentTool(inner, name="inner")
        result = await tool.run(task="do something")
        assert "result from inner" in result

    @pytest.mark.asyncio
    async def test_agent_tool_spec(self):
        from chainforge.core.agent import Agent
        from chainforge.agents.agent_tool import AgentTool

        inner = Agent(llm=FakeLLM())
        tool = AgentTool(inner, name="specialist", description="A specialist agent")
        spec = tool.spec
        assert spec.name == "specialist"
        assert spec.description == "A specialist agent"


class TestAgentChain:
    @pytest.mark.asyncio
    async def test_chain_creation(self):
        from chainforge.agents.agent_chain import AgentChain
        from chainforge.core.agent import Agent

        chain = AgentChain(name="test_chain")
        chain.add_step("step1", Agent(llm=FakeLLM("output1")), "First step")
        chain.add_step("step2", Agent(llm=FakeLLM("output2")), "Second step")
        assert len(chain.steps) == 2
        assert chain.steps[0].name == "step1"

    @pytest.mark.asyncio
    async def test_chain_run(self):
        from chainforge.agents.agent_chain import AgentChain
        from chainforge.core.agent import Agent

        chain = AgentChain(name="test")
        chain.add_step("a", Agent(llm=FakeLLM("result a")))
        chain.add_step("b", Agent(llm=FakeLLM("result b")))

        stream = await chain.run("start")
        events = await stream.collect()
        assert any(e.type.value == "done" for e in events)

    @pytest.mark.asyncio
    async def test_chain_state_events(self):
        from chainforge.agents.agent_chain import AgentChain
        from chainforge.core.agent import Agent

        chain = AgentChain(name="test")
        chain.add_step("a", Agent(llm=FakeLLM("ok")))
        stream = await chain.run("go")
        events = await stream.collect()
        states = [e.data.get("state") for e in events if e.type.value == "state"]
        assert "chain_start" in states
        assert "step_start" in states
        assert "step_done" in states
        assert "chain_done" in states

    @pytest.mark.asyncio
    async def test_chain_to_tool(self):
        from chainforge.agents.agent_chain import AgentChain
        from chainforge.core.agent import Agent

        chain = AgentChain(name="test")
        chain.add_step("a", Agent(llm=FakeLLM("ok")))
        tool = chain.to_tool("my_chain", "A chain tool")
        assert tool.spec.name == "my_chain"


class TestAgentHub:
    def test_register_and_get(self):
        from chainforge.agents.agent_hub import AgentHub
        from chainforge.core.agent import Agent

        hub = AgentHub()
        hub.register("search", Agent(llm=FakeLLM()), "Search agent", tags=["research"])
        assert hub.get("search") is not None
        assert hub.count == 1

    def test_list(self):
        from chainforge.agents.agent_hub import AgentHub
        from chainforge.core.agent import Agent

        hub = AgentHub()
        hub.register("a", Agent(llm=FakeLLM()), "Agent A")
        hub.register("b", Agent(llm=FakeLLM()), "Agent B")
        assert len(hub.list()) == 2

    def test_search(self):
        from chainforge.agents.agent_hub import AgentHub
        from chainforge.core.agent import Agent

        hub = AgentHub()
        hub.register("weather", Agent(llm=FakeLLM()), "Weather forecast")
        hub.register("search", Agent(llm=FakeLLM()), "Search the web")
        results = hub.search("weather")
        assert len(results) >= 1

    def test_find_by_tag(self):
        from chainforge.agents.agent_hub import AgentHub
        from chainforge.core.agent import Agent

        hub = AgentHub()
        hub.register("a", Agent(llm=FakeLLM()), "Agent A", tags=["demo"])
        hub.register("b", Agent(llm=FakeLLM()), "Agent B", tags=["prod"])
        assert len(hub.find_by_tag("demo")) == 1
        assert len(hub.find_by_tag("prod")) == 1

    def test_summary(self):
        from chainforge.agents.agent_hub import AgentHub
        from chainforge.core.agent import Agent

        hub = AgentHub()
        hub.register("x", Agent(llm=FakeLLM()), "Agent X")
        summary = hub.summary()
        assert "Agent X" in summary
        assert "1 agents" in summary

    def test_clear(self):
        from chainforge.agents.agent_hub import AgentHub
        from chainforge.core.agent import Agent

        hub = AgentHub()
        hub.register("a", Agent(llm=FakeLLM()))
        hub.clear()
        assert hub.count == 0

    @pytest.mark.asyncio
    async def test_create_router(self):
        from chainforge.agents.agent_hub import AgentHub
        from chainforge.core.agent import Agent

        hub = AgentHub()
        hub.register("search", Agent(llm=FakeLLM("search result")))
        hub.register("calc", Agent(llm=FakeLLM("calc result")))

        router = hub.create_router(classifier_llm=FakeLLM("search"))
        stream = await router.run("Find something")
        events = await stream.collect()
        assert any(e.type.value == "done" for e in events)

    def test_create_chain(self):
        from chainforge.agents.agent_hub import AgentHub
        from chainforge.core.agent import Agent

        hub = AgentHub()
        hub.register("a", Agent(llm=FakeLLM("out_a")))
        hub.register("b", Agent(llm=FakeLLM("out_b")))
        chain = hub.create_chain(["a", "b"], name="test")
        assert chain.name == "test"
        assert len(chain.steps) == 2


class TestLinkingImports:
    def test_all_importable(self):
        from chainforge.agents import AgentTool, AgentChain, ChainTool, AgentHub
        assert AgentTool is not None
        assert AgentChain is not None
        assert ChainTool is not None
        assert AgentHub is not None
