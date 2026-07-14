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
"""Cache protocol and entry types for LLM response caching."""

from __future__ import annotations

import datetime
import hashlib
import json
from typing import Any, Protocol

from pydantic import BaseModel, Field

from chainforge.core.message import Message


class CacheEntry(BaseModel):
    """A cached LLM response with metadata."""

    key: str = Field(description="Cache key")
    value: str = Field(description="Cached response content")
    created_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    ttl: int = Field(default=300, description="Time-to-live in seconds (0 = no expiry)")
    hit_count: int = Field(default=0, description="Number of cache hits")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Cache metadata")

    @property
    def is_expired(self) -> bool:
        if self.ttl <= 0:
            return False
        created = datetime.datetime.fromisoformat(self.created_at)
        elapsed = (datetime.datetime.now(datetime.timezone.utc) - created).total_seconds()
        return elapsed > self.ttl


def make_cache_key(
    model: str,
    messages: list[Message],
    tools: list | None = None,
) -> str:
    """Generate a deterministic cache key from LLM inputs.

    Args:
        model: Model name.
        messages: Message list.
        tools: Tool specifications (optional).

    Returns:
        SHA-256 hex digest.
    """
    parts = [model]
    for m in messages:
        parts.append(f"{m.role}:{m.content or ''}")
    if tools:
        tool_names = sorted(t.spec.name if hasattr(t, "spec") else str(t) for t in tools)
        parts.append("|".join(tool_names))
    key_input = "||".join(parts)
    return hashlib.sha256(key_input.encode()).hexdigest()


class BaseCache(Protocol):
    """Protocol for cache implementations."""

    async def get(self, key: str) -> str | None:
        """Get a cached value. Returns None if not found or expired."""
        ...

    async def set(self, key: str, value: str, ttl: int = 300) -> None:
        """Set a cache entry with TTL."""
        ...

    async def clear(self, key: str | None = None) -> None:
        """Clear a specific key, or all entries if key is None."""
        ...

    async def stats(self) -> dict[str, Any]:
        """Return cache statistics."""
        ...
