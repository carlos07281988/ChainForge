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
"""Callback protocol — structured observability hooks for the Agent loop.

Callbacks provide one-way notification at key points in agent execution.
Unlike Middleware (which modifies the stream) or ReasoningStrategy (which
modifies behavior), Callbacks are purely observational — they listen
and record, but cannot change execution.

Register callbacks on any Agent:
    agent = Agent(llm=llm, callbacks=[LoggingCallback(), MetricsCallback()])
"""

from __future__ import annotations

from typing import Any, Protocol


class Callback(Protocol):
    """Protocol for agent lifecycle callbacks.

    All methods are optional; implement only the ones you need.
    Callbacks are async, fire-and-forget: exceptions are caught
    and logged so they never break the agent loop.
    """

    name: str = "callback"

    async def on_agent_start(self, prompt: str, context: dict[str, Any] | None = None) -> None:
        """Called when the agent begins processing a prompt."""

    async def on_agent_end(self, output: str, context: dict[str, Any] | None = None) -> None:
        """Called when the agent completes successfully."""

    async def on_llm_start(self, messages: list, context: dict[str, Any] | None = None) -> None:
        """Called before each LLM generation call."""

    async def on_llm_end(self, response: Any, context: dict[str, Any] | None = None) -> None:
        """Called after each LLM generation call."""

    async def on_tool_start(self, tool_name: str, args: dict[str, Any], context: dict[str, Any] | None = None) -> None:
        """Called when a tool starts executing."""

    async def on_tool_end(self, tool_name: str, result: str, context: dict[str, Any] | None = None) -> None:
        """Called after a tool completes execution."""

    async def on_error(self, error: Exception, context: dict[str, Any] | None = None) -> None:
        """Called when an error occurs during agent execution."""


class BaseCallback:
    """Convenience base class with empty implementations for all hooks.

    Subclass this and override only the methods you need.

    Usage:
        class MyCallback(BaseCallback):
            async def on_llm_start(self, messages, context=None):
                print(f"LLM call with {len(messages)} messages")
    """

    name: str = "base_callback"

    async def on_agent_start(self, prompt: str, context: dict | None = None) -> None:
        pass

    async def on_agent_end(self, output: str, context: dict | None = None) -> None:
        pass

    async def on_llm_start(self, messages: list, context: dict | None = None) -> None:
        pass

    async def on_llm_end(self, response: Any, context: dict | None = None) -> None:
        pass

    async def on_tool_start(self, tool_name: str, args: dict, context: dict | None = None) -> None:
        pass

    async def on_tool_end(self, tool_name: str, result: str, context: dict | None = None) -> None:
        pass

    async def on_error(self, error: Exception, context: dict | None = None) -> None:
        pass
