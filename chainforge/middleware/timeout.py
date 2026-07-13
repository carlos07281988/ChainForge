"""Timeout middleware — enforce a maximum duration for agent execution."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from chainforge.core.message import Message
from chainforge.core.stream import EventType, StreamEvent


def timeout_middleware(timeout_seconds: float = 60.0):
    """Create a middleware that enforces a timeout on agent execution.

    Args:
        timeout_seconds: Maximum execution time before raising TimeoutError.
    """

    async def _timeout_mw(
        messages: list[Message],
        ctx: dict[str, Any],
        next_handler,
    ) -> AsyncIterator[StreamEvent]:
        try:
            async with asyncio.timeout(timeout_seconds):
                async for event in next_handler(messages, ctx):
                    yield event
        except asyncio.TimeoutError:
            yield StreamEvent(
                type=EventType.error,
                content=f"Agent execution timed out after {timeout_seconds}s",
            )

    return _timeout_mw
