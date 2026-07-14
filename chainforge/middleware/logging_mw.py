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
"""Logging middleware — structured logging of agent execution.

Logs input, output, tool calls (with timing), state transitions,
and errors. Integrates with ``chainforge.logging.configure_logging``.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from logging import DEBUG, INFO, WARNING, ERROR
from typing import Any

from chainforge.core.message import Message
from chainforge.core.stream import EventType, StreamEvent
from chainforge.logging import get_logger, log_data


def logging_middleware(
    logger_name: str = "agent",
    log_level: int = INFO,
    log_input: bool = True,
    log_output: bool = True,
    log_tool_calls: bool = True,
    log_states: bool = True,
    max_input_length: int = 500,
):
    """Middleware that logs agent execution in a structured way.

    Args:
        logger_name: Name for the logger (under ``chainforge.*``).
        log_level: Log level for routine events.
        log_input: Log the user prompt at start.
        log_output: Log the final response at end.
        log_tool_calls: Log each tool call and result.
        log_states: Log agent state transitions.
        max_input_length: Truncate logged input/output to this many chars.

    Usage:
        from chainforge.middleware.logging_mw import logging_middleware

        agent = Agent(
            llm=...,
            middlewares=[logging_middleware()],
        )
    """
    logger = get_logger(logger_name)

    async def _middleware(
        messages: list[Message],
        ctx: dict[str, Any],
        next_handler,
    ) -> AsyncIterator[StreamEvent]:
        run_id = f"run_{time.monotonic_ns()}"
        start = time.monotonic()
        tool_calls: list[dict] = []
        text_parts: list[str] = []

        # Log input
        if log_input and messages:
            last = messages[-1]
            content = (last.content or "")[:max_input_length]
            log_data(logger, log_level, f"[{run_id}] Agent started",
                     data={"input": content, "messages": len(messages)})

        async for event in next_handler(messages, ctx):
            if event.type == EventType.text and event.content:
                text_parts.append(event.content)
                if log_output:
                    log_data(logger, DEBUG, f"[{run_id}] token",
                             data={"text": event.content[:200]})

            elif event.type == EventType.tool_call and log_tool_calls:
                tc_info = {
                    "name": event.data.get("name"),
                    "args": event.data.get("args"),
                }
                tool_calls.append(tc_info)
                log_data(logger, log_level, f"[{run_id}] tool → {tc_info['name']}",
                         data={"tool_call": tc_info})

            elif event.type == EventType.tool_result and log_tool_calls:
                log_data(logger, log_level, f"[{run_id}] tool ← {event.data.get('name')}",
                         data={"tool_result": {
                             "name": event.data.get("name"),
                             "length": len(event.data.get("content", "") or ""),
                             "is_error": event.data.get("is_error", False),
                         }})

            elif event.type == EventType.state and log_states:
                log_data(logger, DEBUG, f"[{run_id}] state → {event.data.get('state')}",
                         data={"state": event.data})

            elif event.type == EventType.error:
                log_data(logger, ERROR, f"[{run_id}] Error: {event.content}",
                         data={"error": event.content})

            yield event

        duration = time.monotonic() - start
        full_text = "".join(text_parts)
        log_data(logger, log_level, f"[{run_id}] Done in {duration:.2f}s",
                 data={
                     "duration_s": round(duration, 3),
                     "tool_calls": len(tool_calls),
                     "tool_names": [tc["name"] for tc in tool_calls if tc.get("name")],
                     "output_length": len(full_text),
                     "output_preview": full_text[:max_input_length],
                 })

    return _middleware
