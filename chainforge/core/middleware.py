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
"""Middleware — composable hooks for cross-cutting concerns.

Middleware wraps agent execution to provide tracing, rate limiting,
retry, logging, or any pre/post processing without polluting agent logic.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import Any

from chainforge.core.message import Message
from chainforge.core.stream import StreamEvent

# Type aliases for middleware (using string annotation for 3.11 compat)
NextHandler = Callable[..., AsyncIterator[StreamEvent]]
"""Signature for the next middleware or final handler."""

MiddlewareFn = Callable[..., AsyncIterator[StreamEvent]]
"""A middleware function: receives messages, context, and next handler."""


class Middleware:
    """Wraps a function as middleware with optional configuration."""

    def __init__(self, fn: MiddlewareFn, name: str | None = None):
        self._fn = fn
        self._name = name or getattr(fn, "__name__", "middleware")

    @property
    def name(self) -> str:
        return self._name

    async def __call__(
        self,
        messages: list[Message],
        ctx: dict[str, Any],
        next_handler: NextHandler,
    ) -> AsyncIterator[StreamEvent]:
        async for event in self._fn(messages, ctx, next_handler):
            yield event


class MiddlewareChain:
    """Compose multiple middleware layers into a single handler chain."""

    def __init__(self, middlewares: list[Middleware | MiddlewareFn]):
        self._middlewares = [Middleware(m) if not isinstance(m, Middleware) else m for m in middlewares]

    async def run(
        self,
        messages: list[Message],
        ctx: dict[str, Any],
        final: NextHandler,
    ) -> AsyncIterator[StreamEvent]:
        """Run middleware chain in order, ending with the final handler."""

        async def _build(index: int) -> NextHandler:
            if index >= len(self._middlewares):
                return final

            middleware = self._middlewares[index]

            async def _next(msgs: list[Message], c: dict[str, Any]) -> AsyncIterator[StreamEvent]:
                next_fn = await _build(index + 1)
                async for event in middleware(msgs, c, next_fn):
                    yield event

            return _next

        handler = await _build(0)
        async for event in handler(messages, ctx):
            yield event
