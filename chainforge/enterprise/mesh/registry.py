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
"""Decentralized registry for mesh peers.

``MeshRegistry`` is an in-memory store that tracks peer nodes across
regions. It supports register, update, unregister, heartbeat-based
offline detection, and capability-aware discovery.
"""

from __future__ import annotations

import time
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# MeshPeer
# ---------------------------------------------------------------------------


class MeshPeer(BaseModel):
    """A peer node registered in the mesh.

    Attributes:
        node_id: Unique node identifier (e.g. ``"us-east-7f3a"``).
        region: Logical region label.
        endpoint: Primary endpoint URL for agent invocation.
        capabilities: List of capability strings advertised by this peer.
        health_check_url: URL for health probing.
        last_seen: Unix timestamp of the last heartbeat or registration.
        status: Current liveness status — ``"online"`` or ``"offline"``.
        metadata: Arbitrary key-value pairs attached by the node.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    node_id: str
    region: str = "unknown"
    endpoint: str = ""
    capabilities: list[str] = Field(default_factory=list)
    health_check_url: str = ""
    last_seen: float = Field(default_factory=time.time)
    status: Literal["online", "offline"] = "online"
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# MeshRegistry
# ---------------------------------------------------------------------------


class MeshRegistry:
    """Decentralized, in-memory peer registry for the agent mesh.

    Typical usage::

        reg = MeshRegistry(heartbeat_timeout=30)
        reg.register(MeshPeer(node_id="n1", region="us-east", capabilities=["chat"]))
        peers = reg.discover(capability="chat")
    """

    def __init__(self, heartbeat_timeout: float = 30.0) -> None:
        self._peers: dict[str, MeshPeer] = {}
        self.heartbeat_timeout = heartbeat_timeout

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def register(self, peer: MeshPeer) -> bool:
        """Insert or update a peer.

        Returns:
            ``True`` if this is a new peer, ``False`` if updated.
        """
        is_new = peer.node_id not in self._peers
        peer.last_seen = time.time()
        peer.status = "online"
        self._peers[peer.node_id] = peer
        return is_new

    def update(
        self,
        node_id: str,
        **fields: Any,
    ) -> MeshPeer | None:
        """Patch mutable fields on an existing peer.

        Supported fields: ``endpoint``, ``capabilities``, ``health_check_url``,
        ``region``, ``metadata``.
        """
        peer = self._peers.get(node_id)
        if peer is None:
            return None
        allowed = {"endpoint", "capabilities", "health_check_url", "region", "metadata"}
        for key, value in fields.items():
            if key in allowed:
                setattr(peer, key, value)
        peer.last_seen = time.time()
        return peer

    def unregister(self, node_id: str) -> bool:
        """Remove a peer from the registry.

        Returns:
            ``True`` if the peer was found and removed.
        """
        if node_id in self._peers:
            del self._peers[node_id]
            return True
        return False

    # ------------------------------------------------------------------
    # Heartbeat / Liveness
    # ------------------------------------------------------------------

    def heartbeat(self, node_id: str) -> bool:
        """Mark a peer as alive by refreshing its ``last_seen`` timestamp.

        Returns:
            ``True`` if the peer was found, ``False`` otherwise.
        """
        peer = self._peers.get(node_id)
        if peer is None:
            return False
        peer.last_seen = time.time()
        peer.status = "online"
        return True

    def check_offline(self) -> list[str]:
        """Mark peers whose heartbeat has timed out as offline.

        Returns:
            List of ``node_id`` values that were transitioned to offline.
        """
        now = time.time()
        newly_offline: list[str] = []
        for peer in self._peers.values():
            if peer.status == "online" and (now - peer.last_seen) > self.heartbeat_timeout:
                peer.status = "offline"
                newly_offline.append(peer.node_id)
        return newly_offline

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def discover(
        self,
        capability: str | None = None,
        region: str | None = None,
        exclude_offline: bool = True,
    ) -> list[MeshPeer]:
        """Find peers matching optional filters.

        Args:
            capability: If set, only peers advertising this capability are returned.
            region: If set, only peers in the given region are returned.
            exclude_offline: When ``True`` (default), offline peers are omitted.

        Returns:
            Matching peers, sorted by most recently seen.
        """
        results: list[MeshPeer] = []
        for peer in self._peers.values():
            if exclude_offline and peer.status == "offline":
                continue
            if capability is not None and capability not in peer.capabilities:
                continue
            if region is not None and peer.region != region:
                continue
            results.append(peer)
        results.sort(key=lambda p: p.last_seen, reverse=True)
        return results

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def list_all(self) -> list[MeshPeer]:
        """Return every registered peer regardless of status."""
        return list(self._peers.values())

    def __len__(self) -> int:
        return len(self._peers)
