"""Rate limit middleware — control the rate of LLM/tool calls.

Uses a token bucket algorithm for smooth rate enforcement.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from typing import Any

from chainforge.core.message import Message
from chainforge.core.stream import EventType, StreamEvent


def rate_limit_middleware(
    calls_per_minute: float = 30,
    burst_size: int | None = None,
):
    """Create a middleware that rate-limits agent execution.

    Args:
        calls_per_minute: Maximum number of LLM calls per minute.
        burst_size: Maximum burst size (defaults to calls_per_minute / 10).
    """
    if burst_size is None:
        burst_size = max(1, int(calls_per_minute / 10))

    interval = 60.0 / calls_per_minute
    tokens = burst_size
    last_refill = time.monotonic()

    async def _rate_limit_mw(
        messages: list[Message],
        ctx: dict[str, Any],
        next_handler,
    ) -> AsyncIterator[StreamEvent]:
        nonlocal tokens, last_refill

        # Refill tokens based on elapsed time
        now = time.monotonic()
        elapsed = now - last_refill
        tokens = min(burst_size, tokens + elapsed * (calls_per_minute / 60))
        last_refill = now

        if tokens < 1:
            wait_time = (1 - tokens) * (60.0 / calls_per_minute)
            yield StreamEvent(
                type=EventType.status,
                content=f"Rate limit reached, waiting {wait_time:.1f}s",
            )
            await asyncio.sleep(wait_time)
            tokens = 1

        tokens -= 1
        async for event in next_handler(messages, ctx):
            yield event

    return _rate_limit_mw
