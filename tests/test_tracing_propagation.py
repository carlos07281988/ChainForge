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
"""Tests for trace context propagation."""

import pytest
from chainforge.tracing.propagation import (
    TraceContext, inject_headers, extract_headers,
    _new_trace_id, _new_span_id,
)


class TestTraceContext:
    def test_default_creation(self):
        ctx = TraceContext()
        assert len(ctx.trace_id) == 32
        assert len(ctx.span_id) == 16
        assert ctx.parent_span_id is None
        assert ctx.trace_flags == "01"

    def test_custom_creation(self):
        ctx = TraceContext(trace_id="a" * 32, span_id="b" * 16)
        assert ctx.trace_id == "a" * 32
        assert ctx.span_id == "b" * 16

    def test_to_traceparent(self):
        ctx = TraceContext(trace_id="a" * 32, span_id="b" * 16, trace_flags="01")
        tp = ctx.to_traceparent()
        assert tp == "00-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-bbbbbbbbbbbbbbbb-01"

    def test_from_traceparent_valid(self):
        tp = "00-0123456789abcdef0123456789abcdef-fedcba9876543210-01"
        ctx = TraceContext.from_traceparent(tp)
        assert ctx is not None
        assert ctx.trace_id == "0123456789abcdef0123456789abcdef"
        assert ctx.span_id == "fedcba9876543210"
        assert ctx.trace_flags == "01"

    def test_from_traceparent_invalid_version(self):
        tp = "01-0123456789abcdef0123456789abcdef-fedcba9876543210-01"
        ctx = TraceContext.from_traceparent(tp)
        assert ctx is None

    def test_from_traceparent_invalid_format(self):
        ctx = TraceContext.from_traceparent("invalid")
        assert ctx is None

    def test_from_traceparent_empty(self):
        ctx = TraceContext.from_traceparent("")
        assert ctx is None

    def test_new_child(self):
        parent = TraceContext(trace_id="a" * 32, span_id="b" * 16)
        child = parent.new_child()
        assert child.trace_id == parent.trace_id
        assert child.span_id != parent.span_id
        assert child.parent_span_id == parent.span_id

    def test_to_dict(self):
        ctx = TraceContext(trace_id="a" * 32, span_id="b" * 16, parent_span_id="c" * 16)
        d = ctx.to_dict()
        assert d["trace_id"] == "a" * 32
        assert d["span_id"] == "b" * 16
        assert d["parent_span_id"] == "c" * 16

    def test_repr(self):
        ctx = TraceContext(trace_id="a" * 32, span_id="b" * 16)
        r = repr(ctx)
        assert "TraceContext" in r
        assert ctx.trace_id[:16] in r


class TestInjectExtract:
    def test_inject_headers(self):
        ctx = TraceContext(trace_id="a" * 32, span_id="b" * 16)
        headers = inject_headers(ctx)
        assert "traceparent" in headers
        assert headers["traceparent"] == ctx.to_traceparent()

    def test_inject_with_existing_headers(self):
        ctx = TraceContext(trace_id="a" * 32, span_id="b" * 16)
        headers = inject_headers(ctx, {"content-type": "application/json"})
        assert headers["content-type"] == "application/json"
        assert "traceparent" in headers

    def test_extract_headers(self):
        tp = "00-0123456789abcdef0123456789abcdef-fedcba9876543210-01"
        ctx = extract_headers({"traceparent": tp})
        assert ctx is not None
        assert ctx.trace_id == "0123456789abcdef0123456789abcdef"

    def test_extract_headers_none(self):
        ctx = extract_headers(None)
        assert ctx is None

    def test_extract_headers_no_trace(self):
        ctx = extract_headers({"content-type": "application/json"})
        assert ctx is None

    def test_roundtrip(self):
        original = TraceContext()
        headers = inject_headers(original)
        extracted = extract_headers(headers)
        assert extracted is not None
        assert extracted.trace_id == original.trace_id
        assert extracted.span_id == original.span_id


class TestIdGeneration:
    def test_new_trace_id_length(self):
        tid = _new_trace_id()
        assert len(tid) == 32
        assert all(c in "0123456789abcdef" for c in tid)

    def test_new_span_id_length(self):
        sid = _new_span_id()
        assert len(sid) == 16
        assert all(c in "0123456789abcdef" for c in sid)

    def test_id_uniqueness(self):
        ids = {_new_trace_id() for _ in range(100)}
        assert len(ids) == 100
