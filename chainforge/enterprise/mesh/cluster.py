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
"""MeshCluster — logical grouping of mesh nodes for fleet management.

A ``MeshCluster`` tracks multiple ``MeshNode`` instances and provides
aggregate health reporting and failover planning.
"""

from __future__ import annotations

from typing import Any

from chainforge.enterprise.mesh.node import MeshNode


class MeshCluster:
    """Manages a collection of ``MeshNode`` instances as one logical cluster.

    Typical usage::

        cluster = MeshCluster(name="production")
        cluster.add_node(us_node)
        cluster.add_node(eu_node)
        summary = cluster.health_summary()
    """

    def __init__(self, name: str = "default") -> None:
        self.name = name
        self._nodes: dict[str, MeshNode] = {}

    # ------------------------------------------------------------------
    # Node management
    # ------------------------------------------------------------------

    def add_node(self, node: MeshNode) -> None:
        """Register a node with this cluster and advertise it to the mesh."""
        self._nodes[node.node_id] = node
        node.advertise()

    def remove_node(self, node_id: str) -> bool:
        """Withdraw and remove a node by ID.

        Returns:
            ``True`` if the node was found and removed.
        """
        node = self._nodes.pop(node_id, None)
        if node is not None:
            node.withdraw()
            return True
        return False

    def get_node(self, node_id: str) -> MeshNode | None:
        """Look up a node by ID."""
        return self._nodes.get(node_id)

    # ------------------------------------------------------------------
    # Health & Status
    # ------------------------------------------------------------------

    def health_summary(self) -> dict[str, Any]:
        """Aggregate health status across all cluster nodes.

        Returns:
            A dict with ``cluster_name``, ``total_nodes``, ``regions``,
            ``nodes`` (per-node health dict), and ``healthy`` (bool).
        """
        nodes_health: list[dict[str, Any]] = []
        regions: set[str] = set()
        all_healthy = True

        for node in self._nodes.values():
            h = node.health()
            nodes_health.append(h)
            regions.add(node.region)
            if h.get("status") != "ok":
                all_healthy = False

        return {
            "cluster_name": self.name,
            "total_nodes": len(self._nodes),
            "regions": sorted(regions),
            "nodes": nodes_health,
            "healthy": all_healthy,
        }

    # ------------------------------------------------------------------
    # Failover planning
    # ------------------------------------------------------------------

    def failover_plan(self) -> dict[str, Any]:
        """Produce a failover map grouping healthy nodes by region.

        For each region, lists the node IDs and capabilities available.
        Also includes a ``total_nodes`` count and the ``cluster_name``.

        Returns:
            Dict keyed by region, each containing a list of node summaries.
        """
        by_region: dict[str, list[dict[str, Any]]] = {}
        total = 0

        for node in self._nodes.values():
            h = node.health()
            total += 1
            by_region.setdefault(node.region, []).append(
                {
                    "node_id": node.node_id,
                    "capabilities": node.capabilities,
                    "status": h.get("status", "unknown"),
                }
            )

        return {
            "cluster_name": self.name,
            "total_nodes": total,
            "by_region": by_region,
        }
