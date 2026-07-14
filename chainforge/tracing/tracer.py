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
"""Tracing — observability for agent execution.

Provides trace/span primitives for monitoring, debugging, and performance analysis.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from pydantic import BaseModel, Field

from chainforge.core.message import Message
from chainforge.core.stream import StreamEvent

# ── Data types ──────────────────────────────────────────────────────────────


class Span(BaseModel):
    """A single span in a trace."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = Field(description="Span name")
    parent_id: str | None = Field(default=None)
    start_time: float = Field(default_factory=time.time)
    end_time: float | None = Field(default=None)
    attributes: dict[str, Any] = Field(default_factory=dict)
    events: list[dict[str, Any]] = Field(default_factory=list)

    @property
    def duration_ms(self) -> float:
        end = self.end_time or time.time()
        return (end - self.start_time) * 1000


class Trace(BaseModel):
    """A complete trace containing multiple spans in a tree."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = Field(default="agent_run")
    spans: list[Span] = Field(default_factory=list)
    start_time: float = Field(default_factory=time.time)
    end_time: float | None = Field(default=None)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def duration_ms(self) -> float:
        end = self.end_time or time.time()
        return (end - self.start_time) * 1000


# ── Tracer protocol ─────────────────────────────────────────────────────────


class Tracer:
    """Base tracer that records spans in memory."""

    def __init__(self, name: str = "chainforge"):
        self._current_trace: Trace | None = None
        self._span_stack: list[Span] = []

    @property
    def current_trace(self) -> Trace | None:
        return self._current_trace

    def start_trace(self, name: str = "agent_run", **metadata: Any) -> Trace:
        trace = Trace(name=name, metadata=metadata)
        self._current_trace = trace
        return trace

    def end_trace(self) -> Trace | None:
        if self._current_trace:
            self._current_trace.end_time = time.time()
        return self._current_trace

    @asynccontextmanager
    async def span(self, name: str, **attrs: Any) -> AsyncIterator[Span]:
        if not self._current_trace:
            self.start_trace(name)

        parent_id = self._span_stack[-1].id if self._span_stack else None
        span = Span(name=name, parent_id=parent_id, attributes=attrs)
        self._current_trace.spans.append(span)
        self._span_stack.append(span)

        try:
            yield span
        finally:
            span.end_time = time.time()
            self._span_stack.pop()

    def event(self, name: str, **attrs: Any) -> None:
        if self._span_stack:
            self._span_stack[-1].events.append({"name": name, "time": time.time(), **attrs})


class ConsoleTracer(Tracer):
    """Tracer that prints spans to console in real-time."""

    def __init__(self, name: str = "chainforge"):
        super().__init__(name)
        self._indent = 0

    @asynccontextmanager
    async def span(self, name: str, **attrs: Any) -> AsyncIterator[Span]:
        prefix = "  " * self._indent
        attrs_str = f" {attrs}" if attrs else ""
        print(f"{prefix}▶ {name}{attrs_str}")

        self._indent += 1
        async with super().span(name, **attrs) as span:
            yield span

        self._indent -= 1
        prefix = "  " * self._indent
        print(f"{prefix}◀ {name} [{span.duration_ms:.1f}ms]")

    def event(self, name: str, **attrs: Any) -> None:
        prefix = "  " * self._indent
        attrs_str = f" {attrs}" if attrs else ""
        print(f"{prefix}· {name}{attrs_str}")


# ── Middleware factory ──────────────────────────────────────────────────────


def trace(tracer: Tracer | None = None) -> Tracer:
    """Get or create a tracer instance."""
    return tracer or Tracer()


def tracing_middleware(tracer: Tracer) -> callable:
    """Create a middleware that traces agent execution.

    Usage:
        from chainforge.tracing import ConsoleTracer, tracing_middleware

        tracer = ConsoleTracer()
        agent = Agent(
            llm=llm,
            tools=[...],
            middlewares=[tracing_middleware(tracer)],
        )
    """
    from chainforge.core.middleware import MiddlewareFn

    async def _tracing_mw(
        messages: list[Message],
        ctx: dict[str, Any],
        next_handler: callable,
    ) -> AsyncIterator[StreamEvent]:
        tracer.start_trace("agent_run")
        async with tracer.span("agent_loop", num_messages=len(messages)):
            async for event in next_handler(messages, ctx):
                if event.type == "tool_call":
                    tracer.event(
                        "tool_call",
                        name=event.data.get("name"),
                        args=event.data.get("args"),
                    )
                elif event.type == "text":
                    tracer.event("token", length=len(event.content or ""))
                yield event
        tracer.end_trace()

    return _tracing_mw
