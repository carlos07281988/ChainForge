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

from chainforge.testing.behavior import BehaviorTest, BehaviorTestRunner, ExpectedBehavior, BehaviorTestResult

__all__.extend(["BehaviorTest", "BehaviorTestRunner", "ExpectedBehavior", "BehaviorTestResult"])
