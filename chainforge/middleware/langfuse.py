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
"""Langfuse middleware — export agent execution traces to Langfuse.

Requires the `langfuse` Python package.
"""

from __future__ import annotations

import os
import time
from collections.abc import AsyncIterator
from typing import Any

from chainforge.core.message import Message
from chainforge.core.stream import EventType, StreamEvent


def langfuse_tracing_middleware(
    secret_key: str | None = None,
    public_key: str | None = None,
    host: str | None = None,
    trace_name: str = "agent_run",
    session_id: str | None = None,
    user_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    release: str | None = None,
):
    """Create a middleware that exports agent execution traces to Langfuse.

    Args:
        secret_key: Langfuse secret key (defaults to LANGFUSE_SECRET_KEY env).
        public_key: Langfuse public key (defaults to LANGFUSE_PUBLIC_KEY env).
        host: Langfuse host URL (defaults to LANGFUSE_HOST env).
        trace_name: Name for the Langfuse trace.
        session_id: Optional session ID for grouping traces.
        user_id: Optional user ID.
        metadata: Additional metadata to attach to the trace.
        release: Release version tag.

    Usage:
        from chainforge.middleware.langfuse import langfuse_tracing_middleware

        agent = Agent(
            llm=llm,
            tools=[...],
            middlewares=[langfuse_tracing_middleware()],
        )
    """
    try:
        from langfuse import Langfuse
    except ImportError:
        raise ImportError(
            "Langfuse middleware requires `langfuse` package. "
            "Install with: pip install 'chainforge[langfuse]'"
        )

    langfuse = Langfuse(
        secret_key=secret_key or os.environ.get("LANGFUSE_SECRET_KEY", ""),
        public_key=public_key or os.environ.get("LANGFUSE_PUBLIC_KEY", ""),
        host=host or os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com"),
    )

    async def _langfuse_middleware(
        messages: list[Message],
        ctx: dict[str, Any],
        next_handler,
    ) -> AsyncIterator[StreamEvent]:
        trace = langfuse.trace(
            name=trace_name,
            session_id=session_id,
            user_id=user_id,
            metadata={
                "message_count": len(messages),
                "input": messages[-1].content if messages else "",
                **(metadata or {}),
            },
            release=release,
            tags=[release] if release else None,
        )

        generation = trace.generation(
            name="agent_loop",
            input=messages[-1].content if messages else "",
            start_time=time.time(),
        )
        tool_call_count = 0
        full_response = ""

        try:
            async for event in next_handler(messages, ctx):
                if event.type == EventType.state:
                    trace.update(
                        metadata={"state": event.data.get("state"), "iteration": event.data.get("iteration")}
                    )
                elif event.type == EventType.tool_call:
                    tool_call_count += 1
                    trace.span(
                        name=f"tool.{event.data.get('name', '?')}",
                        input=event.data.get("args"),
                    )
                elif event.type == EventType.text and event.content:
                    full_response += event.content
                elif event.type == EventType.error:
                    generation.update(
                        level="ERROR",
                        status_message=event.content or "Unknown error",
                        end_time=time.time(),
                    )
                yield event

            generation.update(
                output=full_response or None,
                usage={"tool_calls": tool_call_count} if tool_call_count else None,
                end_time=time.time(),
            )

        except Exception as e:
            generation.update(
                level="ERROR",
                status_message=str(e),
                end_time=time.time(),
            )
            raise

        finally:
            trace.update(end_time=time.time())

    return _langfuse_middleware
