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
"""GraphMemory — Graph-native Agent Memory. Replaces vector memory with graph structure.

Usage:
    memory = GraphMemory(engine=engine)
    memory.remember("user", "carlos", metadata={"email": "carlos@example.com"})
    memory.link("carlos", "order-123", "PURCHASED")
    context = memory.recall("carlos", depth=2)
"""

from __future__ import annotations

import time
from typing import Any

from chainforge.enterprise.graphrag.engine import GraphRAGEngine
from chainforge.enterprise.graphrag.models import Edge, Node


class GraphMemory:
    """Graph-native Agent Memory — replaces vector memory with graph structure.

    Usage:
        memory = GraphMemory(engine=engine)
        memory.remember("user", "carlos", metadata={"email": "carlos@example.com"})
        memory.link("carlos", "order-123", "PURCHASED")
        context = memory.recall("carlos", depth=2)
    """

    def __init__(self, engine: GraphRAGEngine):
        self._engine = engine

    def remember(
        self, entity_type: str, label: str, metadata: dict[str, Any] | None = None
    ) -> Node:
        """Store a fact as a graph node. Existing node is updated."""
        existing = self._engine.get_node_by_label(label, entity_type)
        if existing:
            node = existing[0]
            node.properties.update(metadata or {})
            node.updated_at = time.time()
            return node
        return self._engine.add_node(
            Node(type=entity_type, label=label, properties=metadata or {})
        )

    def link(
        self,
        source_label: str,
        target_label: str,
        relation_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> Edge | None:
        """Create a relationship between two entity labels."""
        src_nodes = self._engine.get_node_by_label(source_label)
        tgt_nodes = self._engine.get_node_by_label(target_label)
        if not src_nodes or not tgt_nodes:
            return None
        return self._engine.add_edge(
            Edge(
                source_id=src_nodes[0].id,
                target_id=tgt_nodes[0].id,
                type=relation_type,
                properties=metadata or {},
            )
        )

    def recall(self, entity_label: str, depth: int = 1) -> dict[str, Any]:
        """Retrieve an entity and its neighbors up to given depth."""
        nodes = self._engine.get_node_by_label(entity_label)
        if not nodes:
            return {"entity": None, "relations": []}
        entity = nodes[0]
        relations: list[dict[str, Any]] = []
        for e in self._engine._graph.edges:
            if e.source_id == entity.id:
                n = self._engine.get_node(e.target_id)
                if n:
                    relations.append(
                        {"type": e.type, "target": n.label, "metadata": e.properties}
                    )
            elif e.target_id == entity.id:
                n = self._engine.get_node(e.source_id)
                if n:
                    relations.append(
                        {
                            "type": e.type + " (incoming)",
                            "source": n.label,
                            "metadata": e.properties,
                        }
                    )
        return {"entity": entity.model_dump(), "relations": relations}

    def forget(self, entity_label: str) -> bool:
        """Remove an entity and its relationships."""
        nodes = self._engine.get_node_by_label(entity_label)
        if not nodes:
            return False
        return self._engine.delete_node(nodes[0].id)
