"""LLM Cache — response caching with TTL and middleware integration.

Provides:
  - InMemoryCache: simple dict-based cache with TTL
  - CacheMiddleware: plug into any Agent's middleware chain
  - make_cache_key: deterministic key generation from LLM inputs

Usage:
    from chainforge.cache import InMemoryCache, CacheMiddleware

    agent = Agent(
        llm=llm,
        middlewares=[CacheMiddleware(cache=InMemoryCache(ttl=3600))],
    )
"""

from chainforge.cache.base import BaseCache, CacheEntry, make_cache_key
from chainforge.cache.memory import InMemoryCache
from chainforge.cache.middleware import CacheMiddleware

__all__ = [
    "BaseCache",
    "CacheEntry",
    "make_cache_key",
    "InMemoryCache",
    "CacheMiddleware",
]
