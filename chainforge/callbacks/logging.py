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
"""Logging callback — logs all agent events via the standard logger."""

from __future__ import annotations

import datetime
from typing import Any

from chainforge.callbacks.base import BaseCallback
from chainforge.logging import get_logger

logger = get_logger("callbacks.logging")


class LoggingCallback(BaseCallback):
    """Logs all agent lifecycle events using ChainForge's structured logger.

    Useful for debugging, auditing, and development.

    Usage:
        from chainforge.callbacks import LoggingCallback

        agent = Agent(llm=llm, callbacks=[LoggingCallback()])
    """

    name: str = "logging"

    async def on_agent_start(self, prompt: str, context: dict | None = None) -> None:
        logger.info(f"Agent started | prompt_len={len(prompt)}")

    async def on_agent_end(self, output: str, context: dict | None = None) -> None:
        logger.info(f"Agent finished | output_len={len(output)}")

    async def on_llm_start(self, messages: list, context: dict | None = None) -> None:
        last = messages[-1] if messages else None
        last_content = str(getattr(last, "content", ""))[:100] if last else ""
        logger.debug(f"LLM call | messages={len(messages)}, last={last_content}")

    async def on_llm_end(self, response: Any, context: dict | None = None) -> None:
        tool_calls = len(getattr(response, "tool_calls", []) or [])
        content_len = len(getattr(response, "content", "") or "")
        logger.debug(f"LLM response | content_len={content_len}, tool_calls={tool_calls}")

    async def on_tool_start(self, tool_name: str, args: dict, context: dict | None = None) -> None:
        logger.info(f"Tool call: {tool_name}({_format_args(args)})")

    async def on_tool_end(self, tool_name: str, result: str, context: dict | None = None) -> None:
        logger.info(f"Tool result: {tool_name} -> {result[:80]}")

    async def on_error(self, error: Exception, context: dict | None = None) -> None:
        logger.error(f"Agent error: {error}", exc_info=True)


def _format_args(args: dict) -> str:
    """Format tool args for logging — truncate long values."""
    parts = []
    for k, v in args.items():
        s = str(v)
        if len(s) > 60:
            s = s[:57] + "..."
        parts.append(f"{k}={s}")
    return ", ".join(parts)
