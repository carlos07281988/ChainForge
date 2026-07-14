"""Cache middleware — automatically caches LLM responses."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from chainforge.cache.base import make_cache_key
from chainforge.cache.memory import InMemoryCache
from chainforge.core.middleware import Middleware
from chainforge.core.message import Message
from chainforge.logging import get_logger

logger = get_logger("cache.middleware")


class CacheMiddleware(Middleware):
    """Middleware that caches LLM responses keyed by (model, messages, tools).

    Usage:
        from chainforge.cache import InMemoryCache, CacheMiddleware

        agent = Agent(
            llm=llm,
            middlewares=[CacheMiddleware(cache=InMemoryCache(default_ttl=300))],
        )
    """

    def __init__(self, cache: InMemoryCache | None = None, ttl: int = 300):
        super().__init__(fn=self._middleware_fn)
        self.cache = cache or InMemoryCache(default_ttl=ttl)
        self.ttl = ttl

    async def _middleware_fn(self, messages, context, next_handler):
        # Try cache hit on first iteration
        model = context.get("model", "") if context else ""
        key = make_cache_key(model, messages)

        cached = await self.cache.get(key)
        if cached is not None:
            logger.debug(f"Cache hit: {key[:16]}...")
            # Yield a single text event from cache
            from chainforge.core.stream import StreamEvent, EventType
            yield StreamEvent(type=EventType.text, content=cached)
            yield StreamEvent(type=EventType.done)
            return

        # Execute and cache the response
        text_parts = []
        async for event in next_handler(messages, context):
            if hasattr(event, "type") and event.type == "text" and event.content:
                text_parts.append(event.content)
            yield event

        if text_parts:
            full_text = "".join(text_parts)
            await self.cache.set(key, full_text, ttl=self.ttl)
            logger.debug(f"Cached response ({len(full_text)} chars): {key[:16]}...")
