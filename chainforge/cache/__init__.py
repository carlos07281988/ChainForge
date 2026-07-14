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
