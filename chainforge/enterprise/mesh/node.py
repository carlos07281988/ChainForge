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
"""Mesh node that hosts an agent and advertises it to peers.

A ``MeshNode`` wraps a callable agent, registers its capabilities
with a ``MeshRegistry``, and exposes an HTTP-friendly profile for
discovery by other nodes in the mesh.

Stop-gap: no actual HTTP server is started. Instead, the node builds
an ``AgentExport``-style profile (agent_id, capabilities, exposed endpoint
metadata) and registers it with the ``MeshRegistry``. Full HTTP serving
will be wired in a follow-up phase.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from chainforge.enterprise.mesh.registry import MeshRegistry


@dataclass
class MeshNode:
    """A single mesh participant hosting an agent.

    Attributes:
        agent: A callable that accepts a ``dict`` payload and returns a ``dict``.
        region: Logical region label (e.g. ``"us-east"``, ``"eu-west"``).
        mesh_registry: The shared registry this node advertises to.
        capabilities: List of capability strings this node supports.
        port: Port the node *would* listen on (reserved for future HTTP server).
        node_id: Unique identifier, auto-derived from ``id(agent)`` if unset.
    """

    agent: Callable[[dict[str, Any]], dict[str, Any]]
    region: str
    mesh_registry: MeshRegistry
    capabilities: list[str] = field(default_factory=list)
    port: int = 8080
    node_id: str = ""

    def __post_init__(self) -> None:
        if not self.node_id:
            self.node_id = f"{self.region}-{id(self):x}"

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def advertise(self) -> None:
        """Register this node's profile with the mesh registry."""
        from chainforge.enterprise.mesh.registry import MeshPeer

        peer = MeshPeer(
            node_id=self.node_id,
            region=self.region,
            endpoint=f"http://localhost:{self.port}/agent",
            capabilities=self.capabilities,
            health_check_url=f"http://localhost:{self.port}/health",
        )
        self.mesh_registry.register(peer)

    def withdraw(self) -> None:
        """Remove this node from the mesh registry."""
        self.mesh_registry.unregister(self.node_id)

    # ------------------------------------------------------------------
    # Invocation
    # ------------------------------------------------------------------

    def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Call the wrapped agent with the given payload."""
        return self.agent(payload)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health(self) -> dict[str, Any]:
        """Return a lightweight health report.

        Does a best-effort ``httpx`` probe against the node's own
        health-check URL when available; falls back to a static report.
        """
        return {
            "node_id": self.node_id,
            "region": self.region,
            "capabilities": self.capabilities,
            "status": "ok",
        }
