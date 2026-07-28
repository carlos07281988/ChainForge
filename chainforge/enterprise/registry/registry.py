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
"""CapabilityRegistry — in-memory store with optional SQLite backend.

Provides agent registration, discovery, health checks, and deprecation.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from chainforge.enterprise.registry.profile import AgentProfile

if TYPE_CHECKING:
    from collections.abc import Iterable


class CapabilityRegistry:
    """Register, discover, and manage agents by capability.

    Attributes:
        backend: Backend store type — ``"memory"`` or ``"sqlite"``.
        namespace: Logical namespace for scoping registrations.
    """

    def __init__(
        self, backend: str = "memory", namespace: str = "default"
    ) -> None:
        self.backend = backend
        self.namespace = namespace
        self._store: dict[str, AgentProfile] = {}
        self._deprecated: dict[str, dict[str, str]] = {}
        self._conn: sqlite3.Connection | None = None
        if backend == "sqlite":
            self._conn = sqlite3.connect(":memory:")
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS agents ("
                "  agent_id TEXT PRIMARY KEY,"
                "  profile_json TEXT NOT NULL"
                ")"
            )
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS deprecated ("
                "  agent_id TEXT,"
                "  version TEXT,"
                "  sunset_date TEXT,"
                "  PRIMARY KEY (agent_id, version)"
                ")"
            )
            self._conn.commit()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def register(self, profile: AgentProfile) -> bool:
        """Upsert an agent profile by ``agent_id``.

        Returns:
            ``True`` if this is a new registration, ``False`` if updated.
        """
        is_new = profile.agent_id not in self._store
        self._store[profile.agent_id] = profile
        if self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO agents(agent_id, profile_json) "
                "VALUES (?, ?)",
                (profile.agent_id, profile.model_dump_json()),
            )
            self._conn.commit()
        return is_new

    def unregister(self, agent_id: str) -> bool:
        """Remove an agent from the registry.

        Returns:
            ``True`` if the agent was found and removed.
        """
        existed = agent_id in self._store
        self._store.pop(agent_id, None)
        self._deprecated.pop(agent_id, None)
        if self._conn:
            self._conn.execute("DELETE FROM agents WHERE agent_id = ?", (agent_id,))
            self._conn.execute(
                "DELETE FROM deprecated WHERE agent_id = ?", (agent_id,)
            )
            self._conn.commit()
        return existed

    def get(self, agent_id: str) -> AgentProfile | None:
        """Retrieve a single agent profile by ID."""
        return self._store.get(agent_id)

    def list_all(self) -> list[AgentProfile]:
        """Return all registered agent profiles."""
        return list(self._store.values())

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def deprecate(self, agent_id: str, version: str, sunset_date: str) -> bool:
        """Mark an agent version as deprecated.

        Returns:
            ``True`` if the agent was found and marked.
        """
        if agent_id not in self._store:
            return False
        self._deprecated.setdefault(agent_id, {})[version] = sunset_date
        if self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO deprecated(agent_id, version, sunset_date) "
                "VALUES (?, ?, ?)",
                (agent_id, version, sunset_date),
            )
            self._conn.commit()
        return True

    async def health_check(self, agent_id: str) -> bool:
        """Synchronous stub — attempts ``httpx.GET`` if available.

        Falls back to returning ``True`` when ``httpx`` is not installed
        or the URL is empty.
        """
        profile = self._store.get(agent_id)
        if not profile or not profile.health_check_url:
            return True
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    profile.health_check_url, timeout=5.0
                )
                return resp.is_success
        except ImportError:
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    async def discover(
        self,
        capability: str | None = None,
        query: str | None = None,
        min_availability: float = 0.0,
        max_latency_ms: int | None = None,
        max_cost: float | None = None,
        tags: list[str] | None = None,
        limit: int = 10,
    ) -> list[tuple[AgentProfile, float]]:
        """Find agents matching the given criteria.

        Scoring algorithm:

        1. Exact capability match gives a base score of 1.0.
        2. If a fuzzy ``query`` is provided, do keyword-overlap scoring
           on ``capabilities``, ``name``, and ``tools_exposed``.
        3. Filter by SLA constraints (availability, latency).
        4. Filter by ``max_cost`` (checks pricing values).
        5. Sort by relevance score descending, apply ``limit``.

        Returns:
            List of ``(profile, score)`` tuples sorted by relevance.
        """
        candidates: Iterable[AgentProfile] = list(self._store.values())

        # Stage 1: exact capability filter
        if capability is not None:
            candidates = [
                p for p in candidates if capability in p.capabilities
            ]

        # Stage 2: fuzzy keyword scoring
        scored: list[tuple[AgentProfile, float]] = []
        for p in candidates:
            if query is not None:
                score = self._keyword_score(p, query)
            elif capability is not None:
                score = 1.0
            else:
                score = 0.0
            scored.append((p, score))

        # Stage 3: SLA filters
        scored = [
            (p, s)
            for p, s in scored
            if p.sla.availability >= min_availability
            and (max_latency_ms is None or p.sla.max_latency_ms <= max_latency_ms)
        ]

        # Stage 4: cost filter
        if max_cost is not None:
            scored = [
                (p, s)
                for p, s in scored
                if self._check_cost(p, max_cost)
            ]

        # Stage 5: sort + limit
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:limit]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _keyword_score(profile: AgentProfile, query: str) -> float:
        """Compute overlap score between query tokens and profile fields."""
        if not query:
            return 0.0
        tokens = set(query.lower().split())
        search_space = set()
        for cap in profile.capabilities:
            search_space.update(cap.lower().replace(":", " ").split())
        search_space.update(profile.name.lower().split())
        for tool in profile.tools_exposed:
            search_space.update(tool.lower().replace("_", " ").split())
        if not tokens or not search_space:
            return 0.0
        overlap = tokens & search_space
        return len(overlap) / len(tokens)

    @staticmethod
    def _check_cost(profile: AgentProfile, max_cost: float) -> bool:
        """Check whether any pricing tier exceeds *max_cost*."""
        if not profile.pricing:
            return True  # no pricing = no cost constraint to fail
        return all(v <= max_cost for v in profile.pricing.values())
