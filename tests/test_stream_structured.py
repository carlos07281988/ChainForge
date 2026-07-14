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
"""Tests for collect_structured on Stream."""

from collections.abc import AsyncIterator

import pytest
from pydantic import BaseModel

from chainforge.core.stream import Stream, StreamEvent
from chainforge.core.message import Message, ToolCall
from chainforge.core.agent import Agent


class WeatherResponse(BaseModel):
    city: str
    temperature: float
    condition: str


class TestCollectStructured:
    @pytest.mark.asyncio
    async def test_collect_structured_direct(self):
        async def _gen() -> AsyncIterator[StreamEvent]:
            yield StreamEvent.text('{"city": "Beijing", "temperature": 28.0, "condition": "Sunny"}')
            yield StreamEvent.done()

        stream = Stream(_gen())
        result = await stream.collect_structured(WeatherResponse)
        assert result is not None
        assert result.city == "Beijing"
        assert result.temperature == 28.0

    @pytest.mark.asyncio
    async def test_collect_structured_no_model_error(self):
        async def _gen() -> AsyncIterator[StreamEvent]:
            yield StreamEvent.text("hello")
            yield StreamEvent.done()

        stream = Stream(_gen())
        with pytest.raises(ValueError, match="No response_model provided"):
            await stream.collect_structured()

    @pytest.mark.asyncio
    async def test_collect_structured_empty(self):
        async def _gen() -> AsyncIterator[StreamEvent]:
            yield StreamEvent.done()

        stream = Stream(_gen())
        result = await stream.collect_structured(WeatherResponse)
        assert result is None

    @pytest.mark.asyncio
    async def test_agent_with_response_model(self):
        """Test that agent.run(response_model=...) passes model to Stream."""

        class FakeLLM:
            model = "fake"
            async def generate(self, messages, tools=None, **kwargs):
                from chainforge.core.llm import LLMResponse
                return LLMResponse(content='{"city": "Paris", "temperature": 22.0, "condition": "Cloudy"}')
            async def stream_generate(self, messages, tools=None, **kwargs):
                yield '{"city": "Paris", "temperature": 22.0, "condition": "Cloudy"}'

        agent = Agent(llm=FakeLLM())
        stream = await agent.run("Weather in Paris?", response_model=WeatherResponse)
        result = await stream.collect_structured()
        assert result is not None
        assert result.city == "Paris"
        assert result.temperature == 22.0
