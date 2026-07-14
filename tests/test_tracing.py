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
"""Tests for the tracing module."""

import pytest

from chainforge.tracing import Tracer, ConsoleTracer, Span


class TestTracer:
    def test_start_trace(self):
        tracer = Tracer()
        trace = tracer.start_trace("test_run")
        assert trace.name == "test_run"
        assert tracer.current_trace is not None

    def test_end_trace(self):
        tracer = Tracer()
        tracer.start_trace("test")
        tracer.end_trace()
        assert tracer.current_trace is not None
        assert tracer.current_trace.end_time is not None

    @pytest.mark.asyncio
    async def test_span(self):
        tracer = Tracer()
        tracer.start_trace("test")
        async with tracer.span("my_span", key="value"):
            pass
        assert len(tracer.current_trace.spans) == 1
        span = tracer.current_trace.spans[0]
        assert span.name == "my_span"
        assert span.attributes.get("key") == "value"
        assert span.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_nested_spans(self):
        tracer = Tracer()
        tracer.start_trace("test")
        async with tracer.span("parent"):
            async with tracer.span("child"):
                pass
        spans = tracer.current_trace.spans
        assert len(spans) == 2
        assert spans[0].name == "parent"
        assert spans[1].name == "child"
        assert spans[1].parent_id == spans[0].id

    def test_event(self):
        tracer = Tracer()
        tracer.start_trace("test")
        import asyncio
        async def _add_span():
            async with tracer.span("test"):
                tracer.event("test_event", value=42)
        asyncio.run(_add_span())
        span = tracer.current_trace.spans[0]
        assert len(span.events) == 1
        assert span.events[0]["name"] == "test_event"

    def test_duration_ms(self):
        span = Span(name="test")
        assert span.duration_ms >= 0


class TestConsoleTracer:
    def test_instantiation(self):
        tracer = ConsoleTracer("test")
        assert tracer is not None
