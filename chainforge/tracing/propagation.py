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
"""Trace context propagation — distributed tracing across agent boundaries.

Implements W3C Trace Context format for cross-agent trace propagation.

Usage:
    from chainforge.tracing.propagation import (
        TraceContext, inject_headers, extract_headers
    )

    # Server side: extract trace context from incoming A2A request
    ctx = extract_headers(request_headers)
    tracer.set_current_context(ctx)

    # Client side: inject trace context into outgoing A2A request
    headers = inject_headers(ctx)
    await client.post(url, headers=headers)
"""

from __future__ import annotations

import uuid
from typing import Any

from chainforge.logging import get_logger

logger = get_logger("tracing.propagation")

# W3C Trace Context header names
TRACE_PARENT_HEADER = "traceparent"
TRACE_STATE_HEADER = "tracestate"


class TraceContext:
    """Represents a distributed trace context.

    Follows the W3C Trace Context specification:
      - trace_id: 32 hex chars (128-bit)
      - span_id: 16 hex chars (64-bit)
      - trace_flags: 2 hex chars (8-bit)
    """

    def __init__(
        self,
        trace_id: str | None = None,
        span_id: str | None = None,
        parent_span_id: str | None = None,
        trace_flags: str = "01",
    ):
        self.trace_id = trace_id or _new_trace_id()
        self.span_id = span_id or _new_span_id()
        self.parent_span_id = parent_span_id
        self.trace_flags = trace_flags

    def new_child(self) -> TraceContext:
        """Create a child span context.

        The child gets a new span_id and the current span_id
        becomes the parent_span_id.
        """
        return TraceContext(
            trace_id=self.trace_id,
            span_id=_new_span_id(),
            parent_span_id=self.span_id,
            trace_flags=self.trace_flags,
        )

    def to_traceparent(self) -> str:
        """Format as W3C traceparent header value.

        Format: ``00-{trace_id}-{span_id}-{trace_flags}``
        """
        return f"00-{self.trace_id}-{self.span_id}-{self.trace_flags}"

    @classmethod
    def from_traceparent(cls, header: str) -> TraceContext | None:
        """Parse a W3C traceparent header value."""
        try:
            parts = header.strip().split("-")
            if len(parts) >= 4 and parts[0] == "00":
                trace_id = parts[1]
                span_id = parts[2]
                flags = parts[3]
                if len(trace_id) == 32 and len(span_id) == 16:
                    return cls(trace_id=trace_id, span_id=span_id, trace_flags=flags)
        except (ValueError, IndexError):
            pass
        return None

    def to_dict(self) -> dict[str, str]:
        """Convert to dict for passing through middleware context."""
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id or "",
        }

    def __repr__(self) -> str:
        return f"TraceContext(trace_id={self.trace_id[:16]}..., span_id={self.span_id})"


def inject_headers(
    context: TraceContext,
    headers: dict[str, str] | None = None,
) -> dict[str, str]:
    """Inject trace context into HTTP headers (for A2A requests).

    Args:
        context: The trace context to propagate.
        headers: Optional existing headers to extend.

    Returns:
        Headers dict with W3C trace context headers.
    """
    headers = headers or {}
    headers[TRACE_PARENT_HEADER] = context.to_traceparent()
    return headers


def extract_headers(headers: dict[str, str] | None) -> TraceContext | None:
    """Extract trace context from HTTP headers (from A2A requests).

    Args:
        headers: HTTP headers dict.

    Returns:
        TraceContext if found, None otherwise.
    """
    if not headers:
        return None
    tp = headers.get(TRACE_PARENT_HEADER) or headers.get(TRACE_PARENT_HEADER.lower()) or headers.get("traceparent")
    if tp:
        return TraceContext.from_traceparent(tp)
    return None


def _new_trace_id() -> str:
    """Generate a new 32-char hex trace ID."""
    return uuid.uuid4().hex


def _new_span_id() -> str:
    """Generate a new 16-char hex span ID."""
    return uuid.uuid4().hex[:16]
