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
"""Mock LLM — simulate LLM responses for testing without API calls."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from chainforge.core.llm import LLMResponse
from chainforge.core.message import Message, Role
from chainforge.logging import get_logger

logger = get_logger("testing.mock_llm")


class MockResponse(BaseModel):
    """A predefined mock response."""
    content: str = Field(default="", description="Text response content")
    tool_calls: list[dict] = Field(default_factory=list, description="Tool calls to simulate")
    finish_reason: str = Field(default="stop", description="Finish reason: stop, tool_calls, length")


class MockLLM(BaseModel):
    """A fake LLM provider that returns predefined responses.

    Useful for testing agent behavior without real API calls.
    Cycles through responses in order; if exhausted, returns the last one.

    Usage:
        llm = MockLLM(responses=[
            MockResponse(content="Hello! How can I help?"),
            MockResponse(
                content="",
                tool_calls=[{"name": "calculate", "args": {"expression": "2+2"}}],
            ),
            MockResponse(content="The answer is 4."),
        ])
        agent = Agent(llm=llm)
    """

    responses: list[MockResponse] = Field(default_factory=lambda: [MockResponse(content="Mock response")])
    call_index: int = Field(default=0, description="Current response index")
    call_history: list[dict] = Field(default_factory=list, description="Record of all calls")

    model_config = {"arbitrary_types_allowed": True}

    @property
    def model(self) -> str:
        return "mock-llm"

    @property
    def total_calls(self) -> int:
        return len(self.call_history)

    async def generate(
        self,
        messages: list[Message],
        tools: list | None = None,
        **kwargs,
    ) -> LLMResponse:
        """Simulate an LLM generation by returning the next predefined response.

        Args:
            messages: The message history (recorded but not used).
            tools: Tool definitions (recorded but not used).
            **kwargs: Additional parameters (recorded but not used).

        Returns:
            The next MockResponse in the sequence, converted to LLMResponse.
        """
        # Record the call
        call_record = {
            "index": self.call_index,
            "messages": [{"role": str(getattr(m, "role", "")), "content": str(getattr(m, "content", ""))[:200]} for m in messages],
            "tools": [t.spec.name if hasattr(t, "spec") else str(t) for t in (tools or [])],
            "kwargs": {k: v for k, v in kwargs.items() if k != "api_key"},
        }
        self.call_history.append(call_record)

        # Get the next response
        response_index = min(self.call_index, len(self.responses) - 1)
        response = self.responses[response_index]
        self.call_index += 1

        logger.debug(f"MockLLM call #{self.call_index}: returned response {response_index}")

        # Build LLMResponse
        tool_calls = None
        if response.tool_calls:
            from chainforge.core.message import ToolCall
            tool_calls = []
            for tc in response.tool_calls:
                name = tc.get("name", "unknown")
                args = tc.get("args", tc.get("arguments", {}))
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {"_raw": args}
                tool_calls.append(ToolCall(
                    id=tc.get("id", f"call_{self.call_index}"),
                    name=name,
                    args=args,
                ))

        # LLMResponse expects tool_calls as list[dict], not ToolCall objects
        tool_calls_dicts = None
        if tool_calls:
            import json as _json
            tool_calls_dicts = [
                {
                    "id": tc.id,
                    "function": {
                        "name": tc.name,
                        "arguments": tc.args if isinstance(tc.args, dict) else {},
                    },
                }
                for tc in tool_calls
            ]

        return LLMResponse(
            content=response.content,
            tool_calls=tool_calls_dicts,
            finish_reason=response.finish_reason,
        )

    def reset(self) -> None:
        """Reset call history and response index."""
        self.call_index = 0
        self.call_history.clear()

    def last_call(self) -> dict | None:
        """Return the most recent call record."""
        return self.call_history[-1] if self.call_history else None

    def assert_called(self, times: int | None = None) -> None:
        """Assert that the LLM was called a specific number of times.

        Args:
            times: Expected call count. If None, just check at least once.
        """
        if times is None:
            assert self.total_calls > 0, "Expected MockLLM to be called at least once"
        else:
            assert self.total_calls == times, f"Expected {times} calls, got {self.total_calls}"

    def assert_last_prompt_contains(self, text: str) -> None:
        """Assert that the last call's last message contains *text*."""
        last = self.last_call()
        assert last is not None, "No calls made"
        last_msg = last["messages"][-1]["content"] if last["messages"] else ""
        assert text in last_msg, f"Expected '{text}' in last prompt, got: {last_msg[:200]}"


# ── Convenience factories ────────────────────────────────────────────────────


def mock_text_response(text: str) -> MockResponse:
    """Create a simple text mock response."""
    return MockResponse(content=text, finish_reason="stop")


def mock_tool_call_response(tool_name: str, args: dict | None = None) -> MockResponse:
    """Create a mock response that triggers a tool call."""
    return MockResponse(
        content="",
        tool_calls=[{"name": tool_name, "args": args or {}}],
        finish_reason="tool_calls",
    )


def mock_agent(
    responses: list[str | dict],
    **kwargs,
) -> tuple[Any, MockLLM]:
    """Create an Agent with a MockLLM for testing.

    Args:
        responses: List of responses. Strings become text responses,
                   dicts become tool call responses.
        **kwargs: Additional Agent parameters.

    Returns:
        (Agent, MockLLM) tuple.
    """
    from chainforge.core.agent import Agent

    mock_responses = []
    for r in responses:
        if isinstance(r, str):
            mock_responses.append(MockResponse(content=r))
        elif isinstance(r, dict):
            mock_responses.append(MockResponse(
                content=r.get("content", ""),
                tool_calls=r.get("tool_calls", []),
                finish_reason=r.get("finish_reason", "stop"),
            ))

    llm = MockLLM(responses=mock_responses)
    agent = Agent.model_construct(llm=llm, **kwargs)
    return agent, llm


# Register MockLLM as a runtime virtual subclass of LLM
try:
    from chainforge.core.llm import LLM as _LLM
    _LLM.register(MockLLM)
except Exception:
    pass
