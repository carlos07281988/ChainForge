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
"""MeshRouter — intelligent peer selection with regional preference and failover.

Given a ``MeshRegistry`` and a requested capability, the router picks
the best peer using a multi-stage scoring algorithm:

1. **Region preference** — same-region peers score higher.
2. **Recency bonus** — peers seen more recently are preferred.
3. **Auto-failover** — if the preferred region has no healthy peers,
   fall back to the closest alternate region based on a simple
   proximity table.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from chainforge.enterprise.mesh.registry import MeshPeer, MeshRegistry


# ---------------------------------------------------------------------------
# Approximate inter-region distance (ms).  Used as a tie-breaker when
# region_preference is not matched and auto_failover is enabled.
# ---------------------------------------------------------------------------

_REGION_PROXIMITY: dict[str, float] = {
    "us-east": 0,
    "us-west": 60,
    "eu-west": 80,
    "eu-central": 90,
    "ap-southeast": 160,
    "ap-northeast": 150,
    "sa-east": 130,
}


class MeshRouter:
    """Select the best peer for a given capability.

    Usage::

        router = MeshRouter()
        peer = router.select(registry, capability="chat", region_preference="us-east")
    """

    @staticmethod
    def _region_distance(region: str) -> float:
        return _REGION_PROXIMITY.get(region, 200.0)

    @staticmethod
    def select(
        registry: MeshRegistry,
        capability: str,
        region_preference: str | None = None,
        auto_failover: bool = True,
    ) -> MeshPeer | None:
        """Pick the best peer matching *capability*.

        Args:
            registry: The mesh registry to query.
            capability: Required capability string.
            region_preference: Preferred region. When provided, same-region
                peers are ranked above all others.
            auto_failover: When ``True`` and no peer is found in the
                preferred region, fall back to peers in other regions
                ordered by proximity.

        Returns:
            The highest-scoring peer, or ``None`` if no peer matches.
        """
        # --- gather candidates ---
        if auto_failover:
            candidates = registry.discover(capability=capability)
        else:
            candidates = registry.discover(
                capability=capability, region=region_preference
            )

        if not candidates:
            return None

        # --- score each candidate ---
        def _score(peer: MeshPeer) -> tuple[float, float]:
            region_bonus = 0.0
            if region_preference:
                if peer.region == region_preference:
                    region_bonus = 1000.0  # same region dominates
                else:
                    # proximity penalty — closer regions lose less
                    dist = MeshRouter._region_distance(peer.region)
                    region_bonus = -dist
            # recency (fresher = higher)
            recency = peer.last_seen
            return (region_bonus, recency)

        best = max(candidates, key=_score)
        return best
