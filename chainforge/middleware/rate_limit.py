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
"""Rate limit middleware — control the rate of LLM/tool calls.

Uses a token bucket algorithm for smooth rate enforcement.

WARNING: The closure state (tokens, last_refill) is shared across ALL calls
using the same middleware function instance, providing global rate limiting.
If you need per-instance rate limiting (e.g., different limits for different
agents), create a separate middleware instance for each agent.

Example:
    # Global rate limit (shared across all agents using this mw)
    global_mw = rate_limit_middleware(calls_per_minute=30)
    agent1 = Agent(..., middlewares=[global_mw])
    agent2 = Agent(..., middlewares=[global_mw])  # shares the same bucket

    # Per-instance rate limit (separate buckets per call)
    mw1 = rate_limit_middleware(calls_per_minute=30, per_instance=True)
    mw2 = rate_limit_middleware(calls_per_minute=30, per_instance=True)
"""

import asyncio
import time
from collections.abc import AsyncIterator
from typing import Any

from chainforge.core.message import Message
from chainforge.core.stream import EventType, StreamEvent


class _TokenBucket:
    """Simple token bucket for rate limiting."""

    def __init__(self, calls_per_minute: float, burst_size: int):
        self.calls_per_minute = calls_per_minute
        self.burst_size = burst_size
        self.tokens = burst_size
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.burst_size, self.tokens + elapsed * (self.calls_per_minute / 60))
        self.last_refill = now

    async def acquire(self) -> float | None:
        """Acquire a token. Returns wait time if waiting is needed, or None."""
        async with self._lock:
            self._refill()
            if self.tokens < 1:
                wait_time = (1 - self.tokens) * (60.0 / self.calls_per_minute)
                self.tokens = 0
                return wait_time
            self.tokens -= 1
            return None


def rate_limit_middleware(
    calls_per_minute: float = 30,
    burst_size: int | None = None,
    per_instance: bool = False,
):
    """Create a middleware that rate-limits agent execution.

    Args:
        calls_per_minute: Maximum number of LLM calls per minute.
        burst_size: Maximum burst size (defaults to calls_per_minute / 10).
        per_instance: When True, each call to this middleware function gets its own
            token bucket (per-call rate limiting). When False (default), the token
            bucket is shared across all calls using the same middleware instance,
            providing global rate limiting.

    The default (per_instance=False) means all agents using the same middleware
    instance share one rate limit. This is useful for global API key rate limits.
    Set per_instance=True for per-agent rate limits.
    """
    if burst_size is None:
        burst_size = max(1, int(calls_per_minute / 10))

    # Shared bucket for global rate limiting (used when per_instance=False)
    _shared_bucket = _TokenBucket(calls_per_minute, burst_size)

    async def _rate_limit_mw(
        messages: list[Message],
        ctx: dict[str, Any],
        next_handler,
    ) -> AsyncIterator[StreamEvent]:
        bucket = _TokenBucket(calls_per_minute, burst_size) if per_instance else _shared_bucket

        wait_time = await bucket.acquire()
        if wait_time is not None:
            yield StreamEvent(
                type=EventType.status,
                content=f"Rate limit reached, waiting {wait_time:.1f}s",
            )
            await asyncio.sleep(wait_time)

        async for event in next_handler(messages, ctx):
            yield event

    return _rate_limit_mw
