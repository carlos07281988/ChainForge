"""Testing utilities — mock LLM and test harness for ChainForge agents.

Usage:
    from chainforge.testing import MockLLM, mock_agent, mock_text_response

    agent, llm = mock_agent(
        responses=["Hello!", {"tool_calls": [{"name": "calculate", "args": {"x": 1}}]}, "Result: 1"],
    )
    async for event in await agent.run("Calculate 1+0"):
        ...
    llm.assert_called(times=3)
"""

from chainforge.testing.mock_llm import (
    MockLLM,
    MockResponse,
    mock_text_response,
    mock_tool_call_response,
    mock_agent,
)

__all__ = [
    "MockLLM",
    "MockResponse",
    "mock_text_response",
    "mock_tool_call_response",
    "mock_agent",
]
