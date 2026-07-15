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

    Handles both cases: no running event loop (sync context) and
    existing running event loop (async context).

    Args:
        coro: The coroutine to execute.

    Returns:
        The return value of the coroutine.
    """
    try:
        loop = asyncio.get_running_loop()
        # Already in async context — schedule a task and wait
        if loop.is_running():
            import threading
            result = []
            error = []

            async def _run():
                try:
                    result.append(await coro)
                except Exception as e:
                    error.append(e)

            future = asyncio.run_coroutine_threadsafe(_run(), loop)
            future.result()  # blocks until done
            if error:
                raise error[0]
            return result[0]
    except RuntimeError:
        pass
    # No event loop running — use asyncio.run()
    return asyncio.run(coro)
