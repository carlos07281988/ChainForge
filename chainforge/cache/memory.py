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
"""In-memory cache implementation."""

from __future__ import annotations

import datetime
from typing import Any

from chainforge.cache.base import CacheEntry
from chainforge.logging import get_logger

logger = get_logger("cache.memory")


class InMemoryCache:
    """Simple in-memory LLM response cache with TTL support.

    Usage:
        cache = InMemoryCache(default_ttl=3600)
        await cache.set("key", "response")
        result = await cache.get("key")  # "response" or None if expired
    """

    def __init__(self, default_ttl: int = 300):
        self._entries: dict[str, CacheEntry] = {}
        self.default_ttl = default_ttl

    async def get(self, key: str) -> str | None:
        """Get a cached value. Returns None if not found or expired."""
        entry = self._entries.get(key)
        if entry is None:
            return None
        if entry.is_expired:
            del self._entries[key]
            return None
        entry.hit_count += 1
        return entry.value

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        """Set a cache entry.

        Args:
            key: Cache key.
            value: Response text.
            ttl: TTL in seconds (default: self.default_ttl).
        """
        self._entries[key] = CacheEntry(
            key=key,
            value=value,
            ttl=ttl if ttl is not None else self.default_ttl,
        )

    async def clear(self, key: str | None = None) -> None:
        """Clear a specific key, or all entries if key is None."""
        if key:
            self._entries.pop(key, None)
        else:
            self._entries.clear()

    async def stats(self) -> dict[str, Any]:
        """Return cache statistics."""
        total = len(self._entries)
        active = sum(1 for e in self._entries.values() if not e.is_expired)
        total_hits = sum(e.hit_count for e in self._entries.values())
        return {
            "total_entries": total,
            "active_entries": active,
            "expired_entries": total - active,
            "total_hits": total_hits,
            "default_ttl": self.default_ttl,
        }

    @property
    def size(self) -> int:
        return len(self._entries)
