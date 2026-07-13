"""Core utilities for the ChainForge framework."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import TypeVar

T = TypeVar("T")


def run_sync(coro: Coroutine[None, None, T]) -> T:
    """Run an async coroutine synchronously using asyncio.run().

    This is useful for synchronous wrappers around async methods,
    replacing the scattered ``import asyncio; asyncio.run(...)`` pattern.

    Args:
        coro: The coroutine to execute.

    Returns:
        The return value of the coroutine.
    """
    return asyncio.run(coro)
