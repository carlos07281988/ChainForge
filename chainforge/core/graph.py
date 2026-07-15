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
"""DAG & CyclicGraph — graph-based execution engines.

DAG (Directed Acyclic Graph) — branch/join pipeline execution.
  - Branching (parallel paths)
  - Joining (merge branches)
  - Conditional routing
  - Cyclic detection (raises on cycles)

CyclicGraph — supports cycles, conditional edges, multi-round execution.
  - Agent loops, reflection, retry circuits
  - Conditional edges with state-driven routing functions
  - Specialized node types (agent, tool, router, conditional, entry, exit, llm)
  - Multi-round execution until terminal node or max_iterations
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from chainforge.core.stream import EventType, Stream, StreamEvent


# ── Shared types ──────────────────────────────────────────────────────────


class DAGNodeType(str, Enum):
    """Node types for the DAG execution engine."""
    step = "step"
    router = "router"
    merge = "merge"
    input = "input"
    output = "output"


class GraphNodeType(str, Enum):
    """Extended node types for CyclicGraph."""
    agent = "agent"
    tool = "tool"
    router = "router"
    conditional = "conditional"
    entry = "entry"
    exit = "exit"
    step = "step"
    merge = "merge"
    llm = "llm"


class Node(BaseModel):
    """A single node in the execution graph."""

    id: str = Field(description="Unique node identifier")
    type: GraphNodeType = Field(default=GraphNodeType.step)
    fn: Any = Field(default=None, description="The callable to execute")
    description: str = Field(default="")


class Edge(BaseModel):
    """A directed edge between nodes."""

    source: str = Field(description="Source node ID")
    target: str = Field(description="Target node ID")
    condition: str | None = Field(default=None, description="Optional condition label for routing")


class GraphContext(BaseModel):
    """Mutable context passed through graph execution."""

    state: dict[str, Any] = Field(default_factory=dict)
    results: dict[str, Any] = Field(default_factory=dict)
    errors: list[dict[str, Any]] = Field(default_factory=list)


# ── DAG — Directed Acyclic Graph ─────────────────────────────────────────


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

    def add_node(self, node_id: str, fn=None, node_type: DAGNodeType = DAGNodeType.step, description: str = "") -> "DAG":
        """Add a node to the graph."""
        self.nodes[node_id] = Node(id=node_id, type=GraphNodeType(node_type.value), fn=fn, description=description)
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
                    input_val = ctx.state.get("input")
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
            ctx.state["input"] = input

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


# ── Conditional Edge (for CyclicGraph) ───────────────────────────────────


class ConditionalEdge(BaseModel):
    """A conditional edge whose target is determined by a routing function.

    routing_fn receives the GraphContext and returns the target node ID
    (or None to stop execution).
    """

    source: str = Field(description="Source node ID")
    routing_fn: Any = Field(description="Callable(context) -> target_node_id | None")
    description: str = Field(default="")

    async def route(self, ctx: GraphContext) -> str | None:
        """Evaluate the routing function and return the target node ID."""
        if callable(self.routing_fn):
            result = self.routing_fn(ctx)
            if hasattr(result, "__await__"):
                result = await result
            return result
        return None


# ── Terminal node type set ───────────────────────────────────────────────

TERMINAL_NODE_TYPES = {GraphNodeType.exit, GraphNodeType.router}


# ── CyclicGraph — supports cycles, conditional edges, multi-round exec ──

class CyclicGraph(BaseModel):
    """Graph execution engine supporting cycles and conditional edges.

    Unlike DAG (which requires acyclic graphs), CyclicGraph supports:
    - Cycles: agent loops, self-reflection, retry circuits
    - Conditional edges: state/routing_fn-driven control flow
    - Specialized node types: agent, tool, router, conditional, entry, exit, llm
    - Multi-round execution: runs until a terminal node (exit/router) is reached
    - Configurable max_iterations to prevent infinite loops

    Usage:
        graph = CyclicGraph(name="agent_loop")
        graph.add_entry("input")
        graph.add_llm("think", fn=llm_call)
        graph.add_node("act", fn=tool_executor, node_type=GraphNodeType.tool)
        graph.add_exit("final", fn=format_output)

        # Conditional routing
        graph.add_conditional_edge(
            "think",
            routing_fn=lambda ctx: "act" if ctx.state.get("needs_tool") else "final",
        )
        graph.add_edge("act", "think")  # cycle back

        stream = graph.run("Hello")
        async for event in stream:
            print(event)
    """

    name: str = Field(default="cyclic_graph")
    nodes: dict[str, Node] = Field(default_factory=dict)
    edges: list[Edge] = Field(default_factory=list)
    conditional_edges: list[ConditionalEdge] = Field(default_factory=list)
    max_iterations: int = Field(default=50, description="Max total node executions")
    max_cycle_depth: int = Field(default=10, description="Max traversals of same node")

    # ── Node management ─────────────────────────────────────────────────

    def add_node(
        self,
        node_id: str,
        fn=None,
        node_type: GraphNodeType = GraphNodeType.step,
        description: str = "",
    ) -> "CyclicGraph":
        if node_id in self.nodes:
            raise ValueError(f"Node '{node_id}' already exists")
        self.nodes[node_id] = Node(id=node_id, type=node_type, fn=fn, description=description)
        return self

    def add_entry(self, node_id: str = "entry", description: str = "Entry point") -> "CyclicGraph":
        return self.add_node(node_id, node_type=GraphNodeType.entry, description=description)

    def add_exit(self, node_id: str = "exit", fn=None, description: str = "Exit point") -> "CyclicGraph":
        return self.add_node(node_id, fn=fn, node_type=GraphNodeType.exit, description=description)

    def add_llm(self, node_id: str, fn=None, description: str = "") -> "CyclicGraph":
        return self.add_node(node_id, fn=fn, node_type=GraphNodeType.llm, description=description)

    def add_agent_node(self, node_id: str, agent_fn, description: str = "") -> "CyclicGraph":
        """Add a node that wraps an entire Agent run."""
        return self.add_node(node_id, fn=agent_fn, node_type=GraphNodeType.agent, description=description)

    def add_tool_node(self, node_id: str, tool_fn, description: str = "") -> "CyclicGraph":
        """Add a node that executes a tool."""
        return self.add_node(node_id, fn=tool_fn, node_type=GraphNodeType.tool, description=description)

    # ── Edge management ─────────────────────────────────────────────────

    def add_edge(self, source: str, target: str, condition: str | None = None) -> "CyclicGraph":
        if source not in self.nodes:
            raise ValueError(f"Source node '{source}' not found")
        if target not in self.nodes:
            raise ValueError(f"Target node '{target}' not found")
        self.edges.append(Edge(source=source, target=target, condition=condition))
        return self

    def add_conditional_edge(
        self,
        source: str,
        routing_fn,
        description: str = "",
    ) -> "CyclicGraph":
        if source not in self.nodes:
            raise ValueError(f"Source node '{source}' not found")
        self.conditional_edges.append(
            ConditionalEdge(source=source, routing_fn=routing_fn, description=description)
        )
        return self

    # ── Graph queries ───────────────────────────────────────────────────

    def _get_outgoing(self, node_id: str) -> list[Edge]:
        return [e for e in self.edges if e.source == node_id]

    def _get_incoming(self, node_id: str) -> list[Edge]:
        return [e for e in self.edges if e.target == node_id]

    def _get_entry_nodes(self) -> list[str]:
        all_targets = {e.target for e in self.edges}
        entry_type_nodes = [nid for nid, n in self.nodes.items() if n.type == GraphNodeType.entry]
        no_incoming = [nid for nid in self.nodes if nid not in all_targets]
        return list(dict.fromkeys(entry_type_nodes + no_incoming))

    def _is_terminal(self, node_id: str) -> bool:
        node = self.nodes.get(node_id)
        if node and node.type in TERMINAL_NODE_TYPES:
            return True
        return not self._get_outgoing(node_id) and not self._has_conditional(node_id)

    def _has_conditional(self, node_id: str) -> bool:
        return any(ce.source == node_id for ce in self.conditional_edges)

    # ── Node execution ──────────────────────────────────────────────────

    async def _execute_node(self, node_id: str, ctx: GraphContext) -> AsyncIterator[StreamEvent]:
        node = self.nodes.get(node_id)
        if node is None:
            yield StreamEvent(type=EventType.error, content=f"Node '{node_id}' not found")
            return

        yield StreamEvent(
            type=EventType.state,
            content=f"executing:{node_id}",
            data={"node": node_id, "type": node.type.value, "description": node.description},
        )

        if node.fn is None:
            return

        try:
            incoming = self._get_incoming(node_id)
            inputs = [ctx.results[e.source] for e in incoming if e.source in ctx.results]

            if node.type == GraphNodeType.entry:
                result = node.fn(ctx.state.get("input", "")) if callable(node.fn) else ctx.state.get("input")
            elif len(inputs) == 0:
                result = node.fn() if callable(node.fn) else node.fn
            elif len(inputs) == 1:
                result = node.fn(inputs[0]) if callable(node.fn) else node.fn
            else:
                result = node.fn(*inputs) if callable(node.fn) else node.fn

            if hasattr(result, "__await__"):
                result = await result

            ctx.results[node_id] = result
            ctx.state["last_result"] = result
            ctx.state["last_node"] = node_id

            if result is not None:
                yield StreamEvent(type=EventType.text, content=str(result))

        except Exception as e:
            ctx.errors.append({"node": node_id, "error": str(e)})
            ctx.state["error"] = str(e)
            yield StreamEvent(type=EventType.error, content=f"Node '{node_id}' failed: {e}")
            raise

    async def _resolve_next(self, node_id: str, ctx: GraphContext) -> str | None:
        """Determine the next node to execute after the given node."""
        # Check conditional edges first
        for ce in self.conditional_edges:
            if ce.source == node_id:
                try:
                    target = await ce.route(ctx)
                    if target is not None:
                        if target not in self.nodes:
                            ctx.errors.append({
                                "node": node_id,
                                "error": f"Conditional route to unknown node '{target}'",
                            })
                            return None
                        return target
                except Exception as e:
                    ctx.errors.append({"node": node_id, "error": f"Routing function failed: {e}"})
                    return None

        # Fall back to static edges
        outgoing = self._get_outgoing(node_id)
        if not outgoing:
            return None
        if len(outgoing) == 1:
            return outgoing[0].target

        # Multiple unconditional edges — ambiguous
        ctx.errors.append({
            "node": node_id,
            "error": f"Multiple unconditional edges from '{node_id}', use conditional edge",
        })
        return None

    # ── Main execution ──────────────────────────────────────────────────

    def run(
        self,
        input: Any = None,
        *,
        initial_node: str | None = None,
        state: dict[str, Any] | None = None,
    ) -> Stream:
        """Execute the CyclicGraph.

        Args:
            input: Initial input (stored in ctx.state["input"]).
            initial_node: Starting node. Auto-detected if None.
            state: Initial state dict to merge in.

        Returns:
            Stream of events.
        """
        async def _generate() -> AsyncIterator[StreamEvent]:
            ctx = GraphContext()
            ctx.state["input"] = input
            if state:
                ctx.state.update(state)

            yield StreamEvent(type=EventType.status, content=f"CyclicGraph '{self.name}' started")

            # Determine start node
            current = initial_node
            if current is None:
                entries = self._get_entry_nodes()
                if not entries:
                    yield StreamEvent(type=EventType.error, content="No entry node found")
                    yield StreamEvent(type=EventType.done)
                    return
                current = entries[0]
                if len(entries) > 1:
                    yield StreamEvent(
                        type=EventType.status,
                        content=f"Multiple entry nodes: {entries}, using '{current}'",
                    )

            visit_count: dict[str, int] = {}
            total_visits = 0

            while current is not None:
                # Cycle prevention
                visit_count[current] = visit_count.get(current, 0) + 1
                if visit_count[current] > self.max_cycle_depth:
                    yield StreamEvent(
                        type=EventType.error,
                        content=f"Max cycle depth ({self.max_cycle_depth}) exceeded for node '{current}'",
                    )
                    break

                total_visits += 1
                if total_visits > self.max_iterations:
                    yield StreamEvent(
                        type=EventType.error,
                        content=f"Max iterations ({self.max_iterations}) exceeded",
                    )
                    break

                # Execute current node
                async for event in self._execute_node(current, ctx):
                    yield event

                # Check if terminal
                if self._is_terminal(current):
                    break

                # Resolve next
                next_node = await self._resolve_next(current, ctx)
                if next_node is None:
                    break

                current = next_node

            yield StreamEvent(
                type=EventType.state,
                content="done",
                data={
                    "state": "done",
                    "graph": self.name,
                    "nodes_executed": total_visits,
                    "errors": len(ctx.errors),
                },
            )
            yield StreamEvent(type=EventType.done)

        return Stream(_generate())

    # ── Agent integration ───────────────────────────────────────────────

    def to_agent_executor(self, agent) -> "CyclicGraph":
        """Create a CyclicGraph that mimics a standard Agent loop.

        Produces an agent-style graph:
          entry -> think -> [has tool_calls?] -> act -> think (cycle)
                          -> exit (no tool_calls)
        """
        from chainforge.core.agent import Agent as ChainForgeAgent
        from chainforge.core.message import Message as CfMessage

        if not isinstance(agent, ChainForgeAgent):
            raise TypeError(f"Expected Agent, got {type(agent).__name__}")

        self.add_entry("entry")

        async def think_fn(messages):
            composed = agent._build_system_prompt()
            if composed:
                msg_list = [CfMessage.system(composed)]
                if isinstance(messages, list):
                    msg_list.extend(messages)
                else:
                    msg_list.append(CfMessage.user(str(messages)))
            elif isinstance(messages, str):
                msg_list = [CfMessage.user(messages)]
            else:
                msg_list = list(messages) if isinstance(messages, list) else [messages]

            kwargs = {}
            if agent.max_tokens is not None:
                kwargs["max_tokens"] = agent.max_tokens
            if agent.temperature is not None:
                kwargs["temperature"] = agent.temperature

            all_tools = agent._all_tools()
            tool_specs = [t.spec for t in all_tools] if all_tools else None
            return await agent.llm.generate(msg_list, tools=tool_specs, **kwargs)

        self.add_llm("think", fn=think_fn)

        async def act_fn(llm_response):
            if not hasattr(llm_response, "tool_calls") or not llm_response.tool_calls:
                return llm_response
            tool_calls = llm_response.tool_calls
            results = await agent._execute_tool_calls(tool_calls)
            return {"results": results, "tool_calls": tool_calls}

        self.add_node("act", fn=act_fn, node_type=GraphNodeType.tool, description="Execute tool calls")
        self.add_exit("exit")

        def routing_fn(ctx):
            result = ctx.results.get("think", {})
            if hasattr(result, "tool_calls") and result.tool_calls:
                return "act"
            return "exit"

        self.add_conditional_edge(
            "think",
            routing_fn=routing_fn,
            description="Route based on tool calls",
        )
        self.add_edge("act", "think")  # cycle back

        return self

    # ── Visualization ───────────────────────────────────────────────────

    def plot(self) -> str:
        lines = [f"CyclicGraph: {self.name}", "=" * (len(self.name) + 13)]
        for node_id, node in self.nodes.items():
            outgoing = [e.target for e in self._get_outgoing(node_id)]
            cond = [ce.description or "cond->?" for ce in self.conditional_edges if ce.source == node_id]
            targets = ", ".join(outgoing + cond) if (outgoing or cond) else "(terminal)"
            lines.append(f"  [{node.type.value}] {node_id} -> {targets}")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return (
            f"CyclicGraph(name={self.name!r}, nodes={len(self.nodes)}, "
            f"edges={len(self.edges)}, cond={len(self.conditional_edges)})"
        )
