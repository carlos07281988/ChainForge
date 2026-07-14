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
"""OpenTelemetry middleware — export agent execution traces to OpenTelemetry.

Requires the `opentelemetry-api` and `opentelemetry-sdk` packages.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Any

from chainforge.core.message import Message
from chainforge.core.stream import EventType, StreamEvent


def otel_tracing_middleware(
    tracer_name: str = "chainforge",
    service_name: str = "chainforge-agent",
    span_attributes: dict[str, Any] | None = None,
):
    """Create a middleware that exports agent execution spans to OpenTelemetry.

    Args:
        tracer_name: Name for the OpenTelemetry tracer.
        service_name: Service name for resource attributes.
        span_attributes: Additional attributes to add to every span.

    Usage:
        from chainforge.middleware.opentelemetry import otel_tracing_middleware

        agent = Agent(
            llm=llm,
            middlewares=[otel_tracing_middleware()],
        )
    """
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import (
            BatchSpanProcessor,
            ConsoleSpanExporter,
        )
    except ImportError:
        raise ImportError(
            "OpenTelemetry middleware requires `opentelemetry-api` and `opentelemetry-sdk`. "
            "Install with: pip install 'chainforge[otel]'"
        )

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)
    tracer = trace.get_tracer(tracer_name)

    async def _otel_middleware(
        messages: list[Message],
        ctx: dict[str, Any],
        next_handler,
    ) -> AsyncIterator[StreamEvent]:
        with tracer.start_as_current_span("agent.run") as span:
            span.set_attribute("messages.count", len(messages))
            if span_attributes:
                for k, v in span_attributes.items():
                    span.set_attribute(k, v)

            tool_call_count = 0
            start_time = time.monotonic()

            async for event in next_handler(messages, ctx):
                if event.type == EventType.tool_call:
                    tool_call_count += 1
                    with tracer.start_as_current_span(f"tool.{event.data.get('name', '?')}") as tool_span:
                        tool_span.set_attribute("tool.name", event.data.get("name", ""))
                        tool_span.set_attribute("tool.args", str(event.data.get("args", {})))
                        yield event

                elif event.type == EventType.error:
                    span.set_attribute("error", True)
                    span.set_attribute("error.message", event.content or "")
                    span.set_status(trace.Status(trace.StatusCode.ERROR, event.content))
                    yield event

                else:
                    yield event

            duration = time.monotonic() - start_time
            span.set_attribute("duration_ms", duration * 1000)
            span.set_attribute("tool_calls.count", tool_call_count)

    return _otel_middleware


def otel_tracing_middleware_light(
    tracer_name: str = "chainforge",
    exporter=None,
):
    """Lightweight OpenTelemetry middleware with custom exporter.

    Args:
        tracer_name: Name for the tracer.
        exporter: Custom SpanExporter. Defaults to ConsoleSpanExporter.

    Usage:
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
        from chainforge.middleware.opentelemetry import otel_tracing_middleware_light

        agent = Agent(
            llm=llm,
            middlewares=[otel_tracing_middleware_light()],
        )
    """
    if exporter is None:
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter
        exporter = ConsoleSpanExporter()

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        raise ImportError("Requires opentelemetry-api and opentelemetry-sdk")

    provider = TracerProvider()
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    tracer = trace.get_tracer(tracer_name)

    async def _mw(messages, ctx, next_handler):
        with tracer.start_as_current_span("agent.run") as span:
            span.set_attribute("messages", len(messages))
            async for event in next_handler(messages, ctx):
                yield event

    return _mw
