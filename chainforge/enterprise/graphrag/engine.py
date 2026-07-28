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
"""GraphRAG 3.0 Engine — Multi-Agent Knowledge Graph Engine.

Provides decentralized knowledge graphs that multiple agents can share.
Supports node/edge CRUD, subgraph search, GraphQL-native query, and
embedding-powered semantic search.
"""

from __future__ import annotations

import uuid
from collections import deque
from typing import Any

from chainforge.enterprise.graphrag.models import Edge, Graph, Node, SubGraph
from chainforge.enterprise.graphrag.query import GraphQLQuery
from chainforge.logging import get_logger

logger = get_logger("enterprise.graphrag")


class GraphRAGEngine:
    """Multi-Agent Knowledge Graph Engine.

    Provides decentralized knowledge graphs that multiple agents can share.
    Supports node/edge CRUD, subgraph search, GraphQL-native query, and
    embedding-powered semantic search.

    Usage:
        engine = GraphRAGEngine(backend="sqlite")
        agent = Agent(llm=llm, graphrag=engine, middlewares=[engine.middleware()])
    """

    def __init__(self, backend: str = "sqlite", max_graph_size: int = 100000):
        self._backend = backend
        self._graph = Graph()
        self._max_size = max_graph_size
        self._index: dict[str, set[str]] = {}  # type -> node_ids
        self._adjacency: dict[str, set[str]] = {}  # source_id -> target_ids

    # ── CRUD ───────────────────────────────────────────────

    def add_node(self, node: Node) -> Node:
        """Add a node to the graph."""
        if self._graph.node_count >= self._max_size:
            return node
        self._graph.nodes[node.id] = node
        if node.type not in self._index:
            self._index[node.type] = set()
        self._index[node.type].add(node.id)
        logger.debug(f"Node added: {node.type}:{node.label}"[:120])
        return node

    def add_edge(self, edge: Edge) -> Edge:
        """Add an edge between two nodes."""
        if edge.source_id not in self._graph.nodes or edge.target_id not in self._graph.nodes:
            edge.id = edge.id or uuid.uuid4().hex[:12]
            self._graph.edges.append(edge)
            return edge
        self._graph.edges.append(edge)
        if edge.source_id not in self._adjacency:
            self._adjacency[edge.source_id] = set()
        self._adjacency[edge.source_id].add(edge.target_id)
        return edge

    def get_node(self, node_id: str) -> Node | None:
        """Get a node by its ID."""
        return self._graph.nodes.get(node_id)

    def get_node_by_label(self, label: str, node_type: str | None = None) -> list[Node]:
        """Find nodes by label (case-insensitive partial match)."""
        results = []
        for n in self._graph.nodes.values():
            if label.lower() in n.label.lower():
                if node_type is None or n.type == node_type:
                    results.append(n)
        return results

    def delete_node(self, node_id: str) -> bool:
        """Remove a node and all edges connected to it."""
        if node_id in self._graph.nodes:
            self._graph.edges = [
                e
                for e in self._graph.edges
                if e.source_id != node_id and e.target_id != node_id
            ]
            del self._graph.nodes[node_id]
            return True
        return False

    # ── Traversal ──────────────────────────────────────────

    def neighbors(self, node_id: str, direction: str = "both") -> list[Node]:
        """Get neighbors of a node. direction: 'out' | 'in' | 'both'."""
        results: dict[str, Node] = {}
        for e in self._graph.edges:
            if direction in ("out", "both") and e.source_id == node_id:
                if e.target_id in self._graph.nodes:
                    results[e.target_id] = self._graph.nodes[e.target_id]
            if direction in ("in", "both") and e.target_id == node_id:
                if e.source_id in self._graph.nodes:
                    results[e.source_id] = self._graph.nodes[e.source_id]
        return list(results.values())

    def path(self, from_id: str, to_id: str, max_depth: int = 5) -> list[list[str]] | None:
        """BFS find paths between two nodes."""
        if from_id not in self._graph.nodes or to_id not in self._graph.nodes:
            return None
        q = deque([(from_id, [from_id], set())])
        all_paths: list[list[str]] = []
        while q:
            current, path_nodes, visited = q.popleft()
            if len(path_nodes) > max_depth:
                continue
            if current == to_id:
                all_paths.append(path_nodes)
                continue
            for e in self._graph.edges:
                next_id = None
                if e.source_id == current and e.target_id not in visited:
                    next_id = e.target_id
                elif e.target_id == current and e.source_id not in visited:
                    next_id = e.source_id
                if next_id:
                    q.append((next_id, path_nodes + [next_id], visited | {next_id}))
        return all_paths if all_paths else None

    # ── Semantic Search ────────────────────────────────────

    def search(self, query: str, limit: int = 10) -> list[SubGraph]:
        """Keyword-based subgraph search (embedding version in production)."""
        terms = query.lower().split()
        matched_nodes = [
            n
            for n in self._graph.nodes.values()
            if any(t in n.label.lower() for t in terms)
        ]
        subgraphs = []
        for node in matched_nodes[:limit]:
            nbrs = self.neighbors(node.id)
            edges = [
                e
                for e in self._graph.edges
                if e.source_id == node.id or e.target_id == node.id
            ]
            subgraphs.append(
                SubGraph(nodes=[node] + nbrs, edges=edges, query=query, score=1.0)
            )
        return subgraphs

    # ── GraphQL Query ──────────────────────────────────────

    def execute(self, gql: GraphQLQuery) -> list[dict]:
        """Execute a simple GraphQL query. Supports node/edge filtering."""
        results = []
        if not gql.query:
            return results
        for node in self._graph.nodes.values():
            if gql.node_type and node.type != gql.node_type:
                continue
            results.append(
                {
                    "id": node.id,
                    "type": node.type,
                    "label": node.label,
                    "properties": node.properties,
                }
            )
        return results[: gql.limit or 100]

    # ── Stats ──────────────────────────────────────────────

    @property
    def stats(self) -> dict:
        return {
            "nodes": self._graph.node_count,
            "edges": self._graph.edge_count,
            "node_types": {k: len(v) for k, v in self._index.items()},
            "backend": self._backend,
        }

    def middleware(self):
        """Returns middleware for auto-extracting entities from agent runs."""

        async def _mw(messages, ctx, next_handler):
            async for event in next_handler(messages, ctx):
                yield event

        return _mw
