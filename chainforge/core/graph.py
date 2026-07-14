# Copyright 2024 ChainForge Contributors
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
"""DAG (Directed Acyclic Graph) — graph-based pipeline execution.

A more flexible alternative to Pipeline that supports:
- Branching (parallel paths)
- Joining (merge branches)
- Conditional routing
- Cyclic detection
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from chainforge.core.stream import EventType, Stream, StreamEvent


class NodeType(str, Enum):
    step = "step"
    router = "router"
    merge = "merge"
    input = "input"
    output = "output"


class Node(BaseModel):
    """A single node in the execution graph."""

    id: str = Field(description="Unique node identifier")
    type: NodeType = Field(default=NodeType.step)
    fn: Any = Field(default=None, description="The callable to execute")
    description: str = Field(default="")


class Edge(BaseModel):
    """A directed edge between nodes."""

    source: str = Field(description="Source node ID")
    target: str = Field(description="Target node ID")
    condition: str | None = Field(default=None, description="Optional condition label for routing")


class GraphContext(BaseModel):
    """Mutable context passed through graph execution."""

    data: dict[str, Any] = Field(default_factory=dict)
    results: dict[str, Any] = Field(default_factory=dict)
    errors: list[dict[str, Any]] = Field(default_factory=list)


class DAG(BaseModel):
    """Directed Acyclic Graph execution engine.

    Usage:
        dag = DAG(name="process")
        dag.add_node("double", fn=lambda x: x * 2)
        dag.add_node("add_one", fn=lambda x: x + 1)
        dag.add_edge("double", "add_one")

        stream = dag.run(42)
        async for event in stream:
            print(event)
    """

    name: str = Field(default="dag")
    nodes: dict[str, Node] = Field(default_factory=dict)
    edges: list[Edge] = Field(default_factory=list)

    def add_node(self, node_id: str, fn=None, node_type: NodeType = NodeType.step, description: str = "") -> "DAG":
        """Add a node to the graph."""
        self.nodes[node_id] = Node(id=node_id, type=node_type, fn=fn, description=description)
        return self

    def add_edge(self, source: str, target: str, condition: str | None = None) -> "DAG":
        """Add a directed edge between two nodes."""
        if source not in self.nodes:
            raise ValueError(f"Source node '{source}' not found")
        if target not in self.nodes:
            raise ValueError(f"Target node '{target}' not found")
        self.edges.append(Edge(source=source, target=target, condition=condition))
        return self

    def _get_outgoing(self, node_id: str, condition: str | None = None) -> list[Edge]:
        return [e for e in self.edges if e.source == node_id and (condition is None or e.condition == condition)]

    def _get_incoming(self, node_id: str) -> list[Edge]:
        return [e for e in self.edges if e.target == node_id]

    def _topological_sort(self) -> list[str]:
        """Return node IDs in topological order (Kahn's algorithm)."""
        in_degree: dict[str, int] = {nid: 0 for nid in self.nodes}
        for edge in self.edges:
            in_degree[edge.target] = in_degree.get(edge.target, 0) + 1

        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        result = []

        while queue:
            node_id = queue.pop(0)
            result.append(node_id)
            for edge in self._get_outgoing(node_id):
                in_degree[edge.target] -= 1
                if in_degree[edge.target] == 0:
                    queue.append(edge.target)

        if len(result) != len(self.nodes):
            raise ValueError("Graph contains a cycle!")

        return result

    def _get_entry_nodes(self) -> list[str]:
        all_targets = {e.target for e in self.edges}
        return [nid for nid in self.nodes if nid not in all_targets]

    def _get_exit_nodes(self) -> list[str]:
        all_sources = {e.source for e in self.edges}
        return [nid for nid in self.nodes if nid not in all_sources]

    async def _execute_node(self, node_id: str, ctx: GraphContext) -> AsyncIterator[StreamEvent]:
        """Execute a single node with proper input handling."""
        node = self.nodes[node_id]
        yield StreamEvent(type=EventType.status, content=f"Node: {node_id} ({node.description or node.type.value})")

        try:
            if node.fn is not None:
                incoming = self._get_incoming(node_id)

                # Entry nodes (no incoming edges) get the global input
                if not incoming:
                    input_val = ctx.data.get("input")
                    result = node.fn(input_val) if callable(node.fn) else node.fn
                else:
                    inputs = [ctx.results[e.source] for e in incoming if e.source in ctx.results]
                    if len(inputs) == 0:
                        result = node.fn() if callable(node.fn) else node.fn
                    elif len(inputs) == 1:
                        result = node.fn(inputs[0]) if callable(node.fn) else node.fn
                    else:
                        result = node.fn(*inputs) if callable(node.fn) else node.fn

                if hasattr(result, "__await__"):
                    result = await result

                ctx.results[node_id] = result
                yield StreamEvent(type=EventType.text, content=str(result) if result is not None else "")

        except Exception as e:
            ctx.errors.append({"node": node_id, "error": str(e)})
            yield StreamEvent(type=EventType.error, content=f"Node '{node_id}' failed: {e}")
            raise

    def run(self, input: Any) -> Stream:
        """Execute the DAG with the given input."""

        async def _generate() -> AsyncIterator[StreamEvent]:
            ctx = GraphContext()
            ctx.data["input"] = input

            yield StreamEvent(type=EventType.status, content=f"DAG '{self.name}' started")

            try:
                order = self._topological_sort()
            except ValueError as e:
                yield StreamEvent(type=EventType.error, content=str(e))
                yield StreamEvent(type=EventType.done)
                return

            yield StreamEvent(type=EventType.status, content=f"Order: {' → '.join(order)}")

            for node_id in order:
                async for event in self._execute_node(node_id, ctx):
                    yield event

            yield StreamEvent(type=EventType.status, content=f"DAG done. {len(ctx.errors)} errors.")
            yield StreamEvent(type=EventType.done)

        return Stream(_generate())

    def __rshift__(self, other: "DAG") -> "DAG":
        combined = DAG(name=f"{self.name} >> {other.name}")
        combined.nodes = {**self.nodes, **other.nodes}
        combined.edges = list(self.edges) + list(other.edges)
        self_exits = self._get_exit_nodes()
        other_entries = other._get_entry_nodes()
        for ex in self_exits:
            for en in other_entries:
                combined.edges.append(Edge(source=ex, target=en))
        return combined

    def plot(self) -> str:
        """Return a simple ASCII visualization of the graph."""
        lines = [f"DAG: {self.name}", "=" * (len(self.name) + 5)]
        for node_id, node in self.nodes.items():
            outgoing = self._get_outgoing(node_id)
            targets = ", ".join(e.target for e in outgoing) if outgoing else "(exit)"
            lines.append(f"  [{node.type.value}] {node_id} → {targets}")
        return "\n".join(lines)
