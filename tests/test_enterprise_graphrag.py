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
"""Tests for the GraphRAG 3.0 module."""

import pytest

from chainforge.enterprise.graphrag.models import Node, Edge
from chainforge.enterprise.graphrag.engine import GraphRAGEngine
from chainforge.enterprise.graphrag.memory import GraphMemory


class TestNodeEdgeModels:
    def test_node_creation(self):
        node = Node(type="Customer", label="Alice", properties={"tier": "premium"})
        assert node.type == "Customer"
        assert node.label == "Alice"
        assert node.properties["tier"] == "premium"

    def test_edge_creation(self):
        edge = Edge(source_id="n1", target_id="n2", type="PURCHASED",
                     label="purchased product", weight=2.0)
        assert edge.source_id == "n1"
        assert edge.target_id == "n2"
        assert edge.type == "PURCHASED"
        assert edge.weight == 2.0


class TestGraphRAGEngine:
    def test_add_node_and_edge(self):
        engine = GraphRAGEngine(backend="memory")
        n1 = Node(type="Person", label="Bob")
        n2 = Node(type="Product", label="Widget")
        engine.add_node(n1)
        engine.add_node(n2)
        engine.add_edge(Edge(source_id=n1.id, target_id=n2.id, type="OWNS"))

        assert engine.get_node(n1.id) is not None
        assert engine.get_node(n2.id) is not None

    def test_stats_tracks_nodes_edges(self):
        engine = GraphRAGEngine(backend="memory")
        n1 = engine.add_node(Node(type="A", label="Node A"))
        n2 = engine.add_node(Node(type="B", label="Node B"))
        engine.add_edge(Edge(source_id=n1.id, target_id=n2.id, type="RELATED"))

        stats = engine.stats
        assert stats["nodes"] == 2
        assert stats["edges"] == 1

    def test_neighbors_returns_correct(self):
        engine = GraphRAGEngine(backend="memory")
        n1 = engine.add_node(Node(type="A", label="Source"))
        n2 = engine.add_node(Node(type="B", label="Target"))
        engine.add_edge(Edge(source_id=n1.id, target_id=n2.id, type="KNOWS"))

        neighbors = engine.neighbors(n1.id, direction="out")
        assert len(neighbors) == 1
        assert neighbors[0].id == n2.id

    def test_path_bfs(self):
        engine = GraphRAGEngine(backend="memory")
        n1 = engine.add_node(Node(type="A", label="Start"))
        n2 = engine.add_node(Node(type="B", label="Mid"))
        n3 = engine.add_node(Node(type="C", label="End"))
        engine.add_edge(Edge(source_id=n1.id, target_id=n2.id, type="GOES_TO"))
        engine.add_edge(Edge(source_id=n2.id, target_id=n3.id, type="GOES_TO"))

        paths = engine.path(n1.id, n3.id, max_depth=3)
        assert paths is not None
        assert len(paths) >= 1
        # Path should be [n1.id, n2.id, n3.id]
        assert paths[0] == [n1.id, n2.id, n3.id]

    def test_delete_node_removes_edges(self):
        engine = GraphRAGEngine(backend="memory")
        n1 = engine.add_node(Node(type="A", label="A"))
        n2 = engine.add_node(Node(type="B", label="B"))
        engine.add_edge(Edge(source_id=n1.id, target_id=n2.id, type="X"))

        assert engine.delete_node(n1.id) is True
        assert engine.get_node(n1.id) is None
        assert engine.stats["edges"] == 0


class TestGraphMemory:
    def test_remember_creates_node(self):
        engine = GraphRAGEngine(backend="memory")
        memory = GraphMemory(engine=engine)
        node = memory.remember("user", "carlos", metadata={"email": "carlos@example.com"})
        assert node.type == "user"
        assert node.label == "carlos"
        assert node.properties["email"] == "carlos@example.com"

    def test_recall_returns_entity_and_relations(self):
        engine = GraphRAGEngine(backend="memory")
        memory = GraphMemory(engine=engine)

        memory.remember("user", "alice")
        memory.remember("order", "order-42")
        memory.link("alice", "order-42", "PURCHASED")

        context = memory.recall("alice")
        assert context["entity"] is not None
        assert context["entity"]["label"] == "alice"
        assert len(context["relations"]) == 1
        assert context["relations"][0]["type"] == "PURCHASED"

    def test_recall_missing_entity_returns_none(self):
        engine = GraphRAGEngine(backend="memory")
        memory = GraphMemory(engine=engine)
        context = memory.recall("nonexistent")
        assert context["entity"] is None
        assert context["relations"] == []
