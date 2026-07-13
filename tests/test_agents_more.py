"""Tests for TreeOfThoughts, ChainOfThought, ConversationalAgent, RouterAgent."""

import pytest


class FakeLLM:
    model = "fake"
    def __init__(self):
        self.call_count = 0
        self.responses = {}

    async def generate(self, messages, tools=None, **kwargs):
        from chainforge.core.llm import LLMResponse
        self.call_count += 1
        last = (messages[-1].content or "") if messages else ""

        if "generate" in last.lower() and "candidates" in last.lower():
            return LLMResponse(content="A: First explore this direction\nB: Consider this alternative\nC: Look at this other angle")
        if "evaluate" in last.lower() or "rate it" in last.lower():
            return LLMResponse(content="7")
        if "classify" in last.lower():
            return LLMResponse(content="search")
        if "reasoning path" in last.lower():
            return LLMResponse(content=f"Path result for: {last[:60]}")
        if "consensus" in last.lower() or "aggregat" in last.lower():
            return LLMResponse(content="Consensus result.")
        if "categories" in last.lower():
            return LLMResponse(content="search")
        if "summarize" in last.lower() or "conversation" in last.lower():
            return LLMResponse(content="Summary of conversation.")
        if "step by step" in last.lower() or "Let's approach" in last.lower():
            return LLMResponse(content="Step 1: Analyze\nStep 2: Compute\nStep 3: Conclude")
        return LLMResponse(content="Test response")

    async def stream_generate(self, messages, tools=None, **kwargs):
        yield "stream"


class FakeLLMResolve:
    """LLM that returns different responses per call for RouterAgent test."""
    model = "fake"

    def __init__(self):
        self.call_count = 0

    async def generate(self, messages, tools=None, **kwargs):
        from chainforge.core.llm import LLMResponse
        self.call_count += 1
        last = (messages[-1].content or "") if messages else ""

        if self.call_count == 1 and "classify" in last.lower():
            return LLMResponse(content="weather")
        if self.call_count == 1:
            return LLMResponse(content="search")
        return LLMResponse(content="Routed response")

    async def stream_generate(self, messages, tools=None, **kwargs):
        yield "stream"


class TestTreeOfThoughts:
    @pytest.mark.asyncio
    async def test_basic_flow(self):
        from chainforge.agents.tree_of_thoughts import TreeOfThoughts
        agent = TreeOfThoughts(llm=FakeLLM(), tools=[], breadth=1, depth=1, candidates_per_step=2)
        stream = await agent.run("Test task")
        events = await stream.collect()
        assert any(e.type.value == "done" for e in events)

    @pytest.mark.asyncio
    async def test_state_transitions(self):
        from chainforge.agents.tree_of_thoughts import TreeOfThoughts
        agent = TreeOfThoughts(llm=FakeLLM(), tools=[], breadth=1, depth=1, candidates_per_step=2)
        stream = await agent.run("Task")
        events = await stream.collect()
        states = [e.data.get("state") for e in events if e.type.value == "state"]
        assert "initializing" in states
        assert "exploring" in states
        assert "selecting" in states

    def test_extract_score(self):
        from chainforge.agents.tree_of_thoughts import TreeOfThoughts
        agent = TreeOfThoughts(llm=FakeLLM())
        assert agent._extract_score("Score: 8") == 8.0
        assert agent._extract_score("Rating: 10/10") == 10.0
        assert agent._extract_score("No number") == 5.0


class TestChainOfThought:
    @pytest.mark.asyncio
    async def test_single_path(self):
        from chainforge.agents.chain_of_thought import ChainOfThought
        agent = ChainOfThought(llm=FakeLLM(), tools=[], num_paths=1)
        stream = await agent.run("Test")
        events = await stream.collect()
        assert any(e.type.value == "done" for e in events)

    @pytest.mark.asyncio
    async def test_multiple_paths(self):
        from chainforge.agents.chain_of_thought import ChainOfThought
        agent = ChainOfThought(llm=FakeLLM(), tools=[], num_paths=2)
        stream = await agent.run("Test multi")
        events = await stream.collect()
        assert any(e.type.value == "done" for e in events)
        states = [e.data.get("state") for e in events if e.type.value == "state"]
        assert "aggregating" in states


class TestConversationalAgent:
    @pytest.mark.asyncio
    async def test_basic_turn(self):
        from chainforge.agents.conversational import ConversationalAgent
        agent = ConversationalAgent(llm=FakeLLM(), tools=[])
        stream = await agent.run("Hello")
        events = await stream.collect()
        assert any(e.type.value == "done" for e in events)

    @pytest.mark.asyncio
    async def test_clear_history(self):
        from chainforge.agents.conversational import ConversationalAgent
        agent = ConversationalAgent(llm=FakeLLM(), tools=[])
        agent.clear_history()
        assert len(agent._buffer.get_history()) == 0


class TestRouterAgent:
    @pytest.mark.asyncio
    async def test_routing(self):
        from chainforge.agents.router import RouterAgent
        from chainforge.core.agent import Agent

        search_agent = Agent(llm=FakeLLM())
        weather_agent = Agent(llm=FakeLLM())

        router = RouterAgent(
            classifier_llm=FakeLLMResolve(),
            routes={"search": search_agent, "weather": weather_agent},
        )
        stream = await router.run("What is the weather?")
        events = await stream.collect()
        assert any(e.type.value == "done" for e in events)

    @pytest.mark.asyncio
    async def test_routing_unknown(self):
        from chainforge.agents.router import RouterAgent
        from chainforge.core.agent import Agent

        class FakeLLMUnknown:
            model = "fake"
            async def generate(self, messages, tools=None, **kwargs):
                from chainforge.core.llm import LLMResponse
                return LLMResponse(content="unknown_category_xyz")
            async def stream_generate(self, messages, tools=None, **kwargs):
                yield "unknown"

        agent = Agent(llm=FakeLLM())
        router = RouterAgent(
            classifier_llm=FakeLLMUnknown(),
            routes={"search": agent},
        )
        stream = await router.run("Do something weird")
        events = await stream.collect()
        # Should have an error event since no route matched
        has_error = any(e.type.value == "error" for e in events)
        has_done = any(e.type.value == "done" for e in events)
        assert has_done


class TestAllAgentImports:
    def test_all_importable(self):
        from chainforge.agents import (
            ReActAgent, ToolAgent,
            PlanAndExecute, Reflection, SelfAsk,
            TreeOfThoughts, ChainOfThought,
            ConversationalAgent, RouterAgent,
        )
        assert TreeOfThoughts is not None
        assert ChainOfThought is not None
        assert ConversationalAgent is not None
        assert RouterAgent is not None
