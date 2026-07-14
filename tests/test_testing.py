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
"""Tests for the testing utilities."""

import pytest
from chainforge.testing import MockLLM, MockResponse, mock_text_response, mock_tool_call_response, mock_agent
from chainforge.core.message import Message, Role
from chainforge.core.llm import LLMResponse


class TestMockResponse:
    def test_defaults(self):
        r = MockResponse()
        assert r.content == ""
        assert r.tool_calls == []
        assert r.finish_reason == "stop"

    def test_text_response(self):
        r = mock_text_response("Hello")
        assert r.content == "Hello"
        assert r.finish_reason == "stop"

    def test_tool_call_response(self):
        r = mock_tool_call_response("calculate", {"x": 1})
        assert r.content == ""
        assert len(r.tool_calls) == 1
        assert r.tool_calls[0]["name"] == "calculate"
        assert r.finish_reason == "tool_calls"


class TestMockLLM:
    @pytest.mark.asyncio
    async def test_generate_text(self):
        llm = MockLLM(responses=[MockResponse(content="Hello!")])
        response = await llm.generate([Message(role=Role.user, content="Hi")])
        assert response.content == "Hello!"
        assert response.finish_reason == "stop"

    @pytest.mark.asyncio
    async def test_generate_tool_call(self):
        llm = MockLLM(responses=[
            MockResponse(content="", tool_calls=[{"name": "calculate", "args": {"x": 1}}], finish_reason="tool_calls"),
        ])
        response = await llm.generate([Message(role=Role.user, content="Calculate")])
        assert response.content == ""
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0]["function"]["name"] == "calculate"

    @pytest.mark.asyncio
    async def test_cycles_through_responses(self):
        llm = MockLLM(responses=[
            MockResponse(content="First"),
            MockResponse(content="Second"),
            MockResponse(content="Third"),
        ])
        r1 = await llm.generate([])
        r2 = await llm.generate([])
        r3 = await llm.generate([])
        assert r1.content == "First"
        assert r2.content == "Second"
        assert r3.content == "Third"

    @pytest.mark.asyncio
    async def test_reuses_last_response_when_exhausted(self):
        llm = MockLLM(responses=[MockResponse(content="Only")])
        await llm.generate([])
        await llm.generate([])
        response = await llm.generate([])
        assert response.content == "Only"

    @pytest.mark.asyncio
    async def test_tracks_call_history(self):
        llm = MockLLM(responses=[MockResponse(content="Hi")])
        await llm.generate([Message(role=Role.user, content="Hello")], tools=["tool1"])
        assert len(llm.call_history) == 1
        assert llm.call_history[0]["index"] == 0
        assert "tools" in llm.call_history[0]

    @pytest.mark.asyncio
    async def test_model_property(self):
        llm = MockLLM()
        assert llm.model == "mock-llm"

    @pytest.mark.asyncio
    async def test_total_calls(self):
        llm = MockLLM(responses=[MockResponse(content="OK")])
        assert llm.total_calls == 0
        await llm.generate([])
        assert llm.total_calls == 1

    @pytest.mark.asyncio
    async def test_reset(self):
        llm = MockLLM(responses=[MockResponse(content="OK"), MockResponse(content="OK2")])
        await llm.generate([])
        assert llm.total_calls == 1
        assert llm.call_index == 1
        llm.reset()
        assert llm.total_calls == 0
        assert llm.call_index == 0

    @pytest.mark.asyncio
    async def test_last_call(self):
        llm = MockLLM(responses=[MockResponse(content="Response")])
        assert llm.last_call() is None
        await llm.generate([Message(role=Role.user, content="Hi")])
        assert llm.last_call() is not None

    def test_assert_called(self):
        llm = MockLLM()
        import asyncio
        asyncio.run(llm.generate([]))
        llm.assert_called(times=1)
        llm.assert_called()  # at least once
        with pytest.raises(AssertionError):
            llm.assert_called(times=2)

    def test_assert_not_called(self):
        llm = MockLLM()
        with pytest.raises(AssertionError):
            llm.assert_called()

    @pytest.mark.asyncio
    async def test_assert_last_prompt_contains(self):
        llm = MockLLM(responses=[MockResponse(content="OK")])
        await llm.generate([Message(role=Role.user, content="What is the weather?")])
        llm.assert_last_prompt_contains("weather")
        with pytest.raises(AssertionError):
            llm.assert_last_prompt_contains("python")


class TestMockAgent:
    @pytest.mark.asyncio
    async def test_mock_agent_creates_agent_and_llm(self):
        agent, llm = mock_agent(
            responses=["Hello!", "How can I help?"],
            system_prompt="You are helpful.",
        )
        assert agent is not None
        assert llm is not None
        assert agent.system_prompt == "You are helpful."
        assert llm.model == "mock-llm"

    @pytest.mark.asyncio
    async def test_mock_agent_with_dict_responses(self):
        agent, llm = mock_agent(
            responses=[
                "Hello",
                {"tool_calls": [{"name": "calculate", "args": {"x": 1}}]},
            ],
        )
        assert len(llm.responses) == 2
        assert llm.responses[0].content == "Hello"
        assert len(llm.responses[1].tool_calls) == 1

    @pytest.mark.asyncio
    async def test_mock_agent_stream_results(self):
        agent, llm = mock_agent(
            responses=["Final answer: 42"],
        )
        stream = await agent.run("What is the answer?")
        texts = []
        async for event in stream:
            if hasattr(event, "type") and event.type == "text" and event.content:
                texts.append(event.content)
        assert any("42" in t for t in texts)

    @pytest.mark.asyncio
    async def test_mock_agent_tool_call_cycle(self):
        from chainforge.core.tool import tool

        call_log = []

        @tool
        def my_tool(x: int) -> str:
            call_log.append(x)
            return f"result: {x}"

        agent, llm = mock_agent(
            responses=[
                {"tool_calls": [{"name": "my_tool", "args": {"x": 42}}], "finish_reason": "tool_calls"},
                "The result is 42",
            ],
            tools=[my_tool],
        )

        stream = await agent.run("Use the tool")
        async for event in stream:
            pass

        assert len(call_log) == 1
        assert call_log[0] == 42
        llm.assert_called(times=2)
