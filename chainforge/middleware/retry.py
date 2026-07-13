"""Retry middleware — automatically retry agent execution on transient failures.

Configurable retry count, delay, and backoff strategy.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from chainforge.core.message import Message
from chainforge.core.stream import EventType, StreamEvent


def retry_middleware(
    max_retries: int = 3,
    base_delay: float = 1.0,
    backoff_factor: float = 2.0,
    retryable_errors: tuple[type[Exception], ...] | None = None,
):
    """Create a middleware that retries on transient errors.

    Args:
        max_retries: Maximum number of retry attempts.
        base_delay: Initial delay in seconds before first retry.
        backoff_factor: Multiplier for delay after each retry.
        retryable_errors: Tuple of exception types to retry on.
            Defaults to (ConnectionError, TimeoutError, OSError).
    """
    if retryable_errors is None:
        retryable_errors = (ConnectionError, TimeoutError, OSError, asyncio.TimeoutError)

    async def _retry_mw(
        messages: list[Message],
        ctx: dict[str, Any],
        next_handler,
    ) -> AsyncIterator[StreamEvent]:
        last_exception: Exception | None = None

        for attempt in range(max_retries + 1):
            if attempt > 0:
                delay = base_delay * (backoff_factor ** (attempt - 1))
                yield StreamEvent(
                    type=EventType.status,
                    content=f"Retry attempt {attempt}/{max_retries} (waiting {delay:.1f}s)",
                )
                await asyncio.sleep(delay)

            try:
                async for event in next_handler(messages, ctx):
                    yield event
                return  # Success
            except retryable_errors as e:
                last_exception = e
                yield StreamEvent(
                    type=EventType.status,
                    content=f"Transient error: {e}. Retrying...",
                )
                continue

        # All retries exhausted
        yield StreamEvent(
            type=EventType.error,
            content=f"All {max_retries} retries exhausted. Last error: {last_exception}",
        )

    return _retry_mw
