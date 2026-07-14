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
"""ReasoningStrategy — composable hooks into the Agent loop.

A reasoning strategy intercepts the agent execution loop at key
decision points, enabling structured thinking patterns without
modifying the agent itself.

Usage:
    class MyStrategy(ReasoningStrategy):
        async def before_llm(self, messages, context):
            messages.append(Message.system("Think carefully!"))
            return messages, context

    agent = Agent(llm=llm, reasoning=[MyStrategy()])
"""

from __future__ import annotations

from typing import Any

from chainforge.logging import get_logger

logger = get_logger("reasoning")


class ReasoningStrategy:
    """Base class for composable reasoning strategies.

    Subclass this and override the hooks you need.
    Each hook is called at the corresponding point in the agent loop.

    Hooks:
      - before_llm: modify messages before LLM call
      - after_llm: modify/process the LLM response
      - on_tool_result: process tool execution results
      - should_stop: decide if the loop should stop early
    """

    name: str = "reasoning_strategy"

    async def before_llm(
        self,
        messages: list,
        context: dict[str, Any] | None = None,
    ) -> tuple[list, dict[str, Any] | None]:
        """Called before each LLM call.

        Override to inject system messages, modify user input, or
        add reasoning instructions.

        Args:
            messages: Current message list.
            context: Execution context dict.

        Returns:
            (messages, context) tuple, possibly modified.
        """
        return messages, context

    async def after_llm(
        self,
        response: Any,
        messages: list,
        context: dict[str, Any] | None = None,
    ) -> tuple[Any, list, dict[str, Any] | None]:
        """Called after each LLM call.

        Override to inspect or modify the LLM response before it's
        processed further (e.g., self-reflection, verification).

        Args:
            response: The LLMResponse from the LLM.
            messages: Current message list.
            context: Execution context dict.

        Returns:
            (response, messages, context) tuple, possibly modified.
        """
        return response, messages, context

    async def on_tool_result(
        self,
        result: Any,
        messages: list,
        context: dict[str, Any] | None = None,
    ) -> tuple[Any, list, dict[str, Any] | None]:
        """Called after a tool execution result is received.

        Override to inspect, log, or skip tool results.

        Args:
            result: The tool result message.
            messages: Current message list.
            context: Execution context dict.

        Returns:
            (result, messages, context) tuple, possibly modified.
        """
        return result, messages, context

    async def should_stop(
        self,
        messages: list,
        context: dict[str, Any] | None = None,
    ) -> bool:
        """Called after each iteration to decide if the loop should stop early.

        Override to implement early stopping based on confidence,
        output quality, or custom criteria.

        Args:
            messages: Current message list.
            context: Execution context dict.

        Returns:
            True to stop the loop, False to continue.
        """
        return False
