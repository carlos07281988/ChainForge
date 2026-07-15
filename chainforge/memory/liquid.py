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
"""Liquid Time-Series Memory — decay-based forgetting with frequency boosting.

Items have continuously decaying weights. Frequently accessed items get boosted.
This simulates human memory: recent and frequent items stay strong, unused fade.

Usage:
    mem = LiquidMemory(decay_rate=0.1, frequency_boost=2.0)
    await mem.add("User prefers dark mode", tags=["preference"])
    context = await mem.get_context(top_k=5)
"""

from __future__ import annotations

import math
import time
from typing import Any

from pydantic import BaseModel, Field


class LiquidItem(BaseModel):
    """A memory item with decaying weight and access tracking."""

    content: str = Field(description="Memory content")
    weight: float = Field(default=1.0, ge=0.0, description="Current weight")
    created_at: float = Field(default_factory=time.time)
    last_accessed: float = Field(default_factory=time.time)
    access_count: int = Field(default=0)
    source: str | None = Field(default=None)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def decay(self, rate: float, now: float | None = None) -> float:
        """Apply exponential decay to weight."""
        now = now or time.time()
        elapsed = now - self.last_accessed
        self.weight *= math.exp(-rate * elapsed)
        self.weight = max(self.weight, 0.01)
        return self.weight

    def boost(self, factor: float = 2.0) -> None:
        """Boost weight on access."""
        self.weight = min(self.weight * factor, 10.0)
        self.access_count += 1
        self.last_accessed = time.time()


class LiquidMemory(BaseModel):
    """Memory with time-based decay and frequency-enhanced retention.

    Items naturally fade unless accessed. Frequently accessed items stay strong.
    This mimics human memory: recall reinforces retention, disuse causes forgetting.

    Usage:
        mem = LiquidMemory(decay_rate=0.05, frequency_boost=1.5)
        await mem.add("Important fact")
        results = await mem.query("fact")
        context = await mem.get_context(top_k=5)
    """

    items: list[LiquidItem] = Field(default_factory=list)
    decay_rate: float = Field(default=0.05, ge=0.0)
    frequency_boost: float = Field(default=1.5, ge=1.0)
    max_items: int = Field(default=1000)
    min_weight: float = Field(default=0.05, ge=0.0)

    async def add(
        self,
        content: str,
        *,
        tags: list[str] | None = None,
        source: str | None = None,
        weight: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> LiquidItem:
        """Add a new item to memory."""
        self._apply_decay()
        item = LiquidItem(
            content=content, weight=weight,
            tags=tags or [], source=source,
            metadata=metadata or {},
        )
        self.items.append(item)
        if len(self.items) > self.max_items:
            self._prune()
        return item

    async def query(self, text: str, *, top_k: int = 5) -> list[dict]:
        """Query by keyword matching, weighted by recency/frequency."""
        self._apply_decay()
        keywords = text.lower().split()
        scored = []

        for item in self.items:
            if item.weight < self.min_weight:
                continue
            content_lower = item.content.lower()
            matches = sum(1 for kw in keywords if kw in content_lower)
            if matches == 0 and keywords:
                continue

            item.boost(self.frequency_boost)
            match_ratio = matches / max(len(keywords), 1)
            score = match_ratio * item.weight * (1 + math.log1p(item.access_count))

            scored.append({
                "content": item.content, "weight": item.weight,
                "score": score, "tags": item.tags,
                "source": item.source, "access_count": item.access_count,
            })

        scored.sort(key=lambda x: -x["score"])
        return scored[:top_k]

    async def get_context(self, *, top_k: int = 10) -> list[dict]:
        """Get highest-weighted context items."""
        self._apply_decay()
        valid = []
        for item in self.items:
            if item.weight < self.min_weight:
                continue
            freq_mult = 1.0 + math.log1p(item.access_count) * 0.5
            effective = item.weight * freq_mult
            valid.append({
                "content": item.content, "weight": item.weight,
                "effective_weight": effective, "tags": item.tags,
                "source": item.source, "access_count": item.access_count,
            })
        valid.sort(key=lambda x: -x["effective_weight"])
        return valid[:top_k]

    async def get_by_tags(self, tags: list[str], *, top_k: int = 10) -> list[dict]:
        """Get items matching specified tags."""
        result = []
        for item in self.items:
            if item.weight < self.min_weight:
                continue
            if any(t in item.tags for t in tags):
                item.boost(self.frequency_boost)
                result.append({
                    "content": item.content, "weight": item.weight,
                    "tags": item.tags, "access_count": item.access_count,
                })
        result.sort(key=lambda x: -x["weight"])
        return result[:top_k]

    async def clear(self) -> None:
        self.items.clear()

    async def stats(self) -> dict:
        """Return memory statistics."""
        self._apply_decay()
        weights = [item.weight for item in self.items]
        return {
            "total_items": len(self.items),
            "avg_weight": sum(weights) / max(len(weights), 1) if weights else 0,
            "max_weight": max(weights) if weights else 0,
            "total_accesses": sum(item.access_count for item in self.items),
            "decay_rate": self.decay_rate,
        }

    def _apply_decay(self) -> None:
        now = time.time()
        for item in self.items:
            item.decay(self.decay_rate, now)

    def _prune(self) -> None:
        self._apply_decay()
        self.items = [item for item in self.items if item.weight >= self.min_weight]


__all__ = ["LiquidMemory", "LiquidItem"]
