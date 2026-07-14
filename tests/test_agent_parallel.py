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
"""Tests for parallel tool execution in Agent."""

import pytest

from chainforge.core.agent import Agent
from chainforge.core.tool import tool


@tool
def slow_tool(delay: float = 0.03) -> str:
    """A tool that simulates latency."""
    import time
    time.sleep(delay)
    return f"slept for {delay}s"


class FakeParallelLLM:
    """LLM that returns multiple tool calls to test parallelism."""
    model = "fake_parallel"

    def __init__(self):
        self.call_count = 0

    async def generate(self, messages, tools=None, **kwargs):
        from chainforge.core.llm import LLMResponse
        if self.call_count == 0:
            self.call_count += 1
            return LLMResponse(
                content="",
                tool_calls=[
                    {"id": "c1", "type": "function", "function": {"name": "slow_tool", "arguments": {"delay": 0.03}}},
                    {"id": "c2", "type": "function", "function": {"name": "slow_tool", "arguments": {"delay": 0.03}}},
                    {"id": "c3", "type": "function", "function": {"name": "slow_tool", "arguments": {"delay": 0.03}}},
                ],
            )
        return LLMResponse(content="Done!")

    async def stream_generate(self, messages, tools=None, **kwargs):
        yield "Done!"


class TestParallelToolExecution:
    @pytest.mark.asyncio
    async def test_parallel_execution_is_faster(self):
        import time
        llm = FakeParallelLLM()
        agent = Agent(llm=llm, tools=[slow_tool], parallel_tool_calls=True)

        start = time.monotonic()
        stream = await agent.run("Run tools")
        await stream.collect()
        elapsed = time.monotonic() - start

        # 3 serial calls at 0.05s each would take >0.15s
        # Parallel should take ~0.05s + overhead
        assert elapsed < 0.25, f"Parallel execution took {elapsed:.3f}s, expected <0.15s"

    @pytest.mark.asyncio
    async def test_serial_execution(self):
        import time
        llm = FakeParallelLLM()
        agent = Agent(llm=llm, tools=[slow_tool], parallel_tool_calls=False)

        start = time.monotonic()
        stream = await agent.run("Run tools serially")
        await stream.collect()
        elapsed = time.monotonic() - start

        # Serial 3 calls at 0.05s each should be >= 0.15s
        assert elapsed >= 0.08, f"Serial execution took {elapsed:.3f}s, expected >=0.12s"
