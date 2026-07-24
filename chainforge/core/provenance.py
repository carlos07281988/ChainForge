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
"""Execution Provenance — causal tracing for agent execution.

Records why each event happened — which input caused which LLM call,
which led to which tool call, which produced which result.

Usage:
    from chainforge.core.provenance import ProvenanceTracker

    tracker = ProvenanceTracker()
    async for event in tracker.track(agent.run(prompt)):
        # events flow through as normal, provenance recorded automatically
        yield event

    # After execution, query the provenance graph
    chain = tracker.trace_decision("tool_call_1")
    graph = tracker.graph()
    path = tracker.critical_path("final_output")
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from chainforge.core.message import Message
from chainforge.core.stream import EventType, StreamEvent

# ── ProvenanceNode model ──────────────────────────────────────────────────


class ProvenanceNode(BaseModel):
    """A single node in the provenance (causal) graph.

    Each node represents an event in agent execution and records what
    caused it, enabling full causal chain tracing.
    """

    id: str = Field(description="Unique node identifier")
    node_type: str = Field(description="llm_call, tool_call, tool_result, "
                                        "user_input, state_transition, error")
    caused_by: str | None = Field(default=None, description="Parent node ID (NULL = root)")
    causal_group: str = Field(default="0", description="Iteration or agent scope")
    data: dict[str, Any] = Field(default_factory=dict, description="Event payload")
    timestamp: float = Field(default_factory=time.time)
    duration_ms: float | None = Field(default=None)

    def path_label(self) -> str:
        """Human-readable label for this node."""
        if self.node_type == "user_input":
            return f'Input: {str(self.data.get("content", ""))[:60]}'
        if self.node_type == "llm_call":
            hints = self.data.get("tool_hints", "")
            return f'LLM: {len(self.data.get("messages", []))} msgs{hints}'
        if self.node_type == "llm_response":
            content = self.data.get("content", "")
            tool_count = len(self.data.get("tool_calls", []))
            label = f'Response: {str(content)[:60]}'
            if tool_count:
                label += f' ({tool_count} tool calls)'
            return label
        if self.node_type == "tool_call":
            return f'Tool: {self.data.get("name", "?")}({self.data.get("args", {})})'
        if self.node_type == "tool_result":
            result = str(self.data.get("content", ""))[:60]
            is_err = self.data.get("is_error", False)
            return f'Result: {result}' + (" [ERROR]" if is_err else "")
        if self.node_type == "state_transition":
            return f'State: {self.data.get("from", "?")} → {self.data.get("to", "?")}'
        if self.node_type == "error":
            return f'Error: {self.data.get("message", "")[:60]}'
        return f'{self.node_type}: {json.dumps(self.data)[:60]}'

    def __repr__(self) -> str:
        causer = f" ← {self.caused_by[:12]}..." if self.caused_by else " (root)"
        return f"ProvNode({self.id[:12]}...: {self.node_type}{causer})"


# ── ProvenanceTracker — causal chain recorder ─────────────────────────────


_NODE_COUNTER: dict[str, int] = {}


def _next_id(prefix: str = "n") -> str:
    _NODE_COUNTER[prefix] = _NODE_COUNTER.get(prefix, 0) + 1
    return f"{prefix}_{_NODE_COUNTER[prefix]}"


class ProvenanceTracker:
    """Records causal provenance during agent execution.

    Wraps an agent's event stream and records ProvenanceNodes for each
    event, linking them causally. After execution, query methods provide
    decision tracing and critical path analysis.

    Usage:
        tracker = ProvenanceTracker(session_id="sess-1")

        # Wrap an agent stream
        async for event in tracker.track(agent.run(prompt)):
            yield event

        # Query results
        chain = tracker.trace_decision("tool_call_3")
        print(tracker.format_chain(chain))
    """

    def __init__(self, session_id: str | None = None,
                 store: "ProvenanceStore | None" = None):
        self._session_id = session_id or f"prov_{uuid.uuid4().hex[:12]}"
        self._nodes: dict[str, ProvenanceNode] = {}
        self._store = store
        self._last_causer: str | None = None  # ID of the last causal node
        self._iteration: int = 0
        self._start_time: float = time.time()

    # ── Public properties ───────────────────────────────────────────────

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def nodes(self) -> list[ProvenanceNode]:
        return list(self._nodes.values())

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    # ── Core: track an event stream ─────────────────────────────────────

    def _record(self, node_type: str, data: dict[str, Any],
                 caused_by: str | None = None,
                 duration_ms: float | None = None) -> ProvenanceNode:
        """Record a provenance node and add it to the graph."""
        node_id = _next_id(node_type)
        node = ProvenanceNode(
            id=node_id,
            node_type=node_type,
            caused_by=caused_by or self._last_causer,
            causal_group=str(self._iteration),
            data=data,
            duration_ms=duration_ms,
        )
        self._nodes[node_id] = node
        self._last_causer = node_id

        # Persist to store if configured
        if self._store:
            self._store.save_node(self._session_id, node)

        return node

    async def track(self, stream: AsyncIterator[StreamEvent],
                     user_prompt: str | None = None,
                     context: dict[str, Any] | None = None
                     ) -> AsyncIterator[StreamEvent]:
        """Wrap an event stream, recording provenance for each event.

        Args:
            stream: The async iterator of StreamEvents from agent.run().
            user_prompt: Optional user prompt text (recorded as root node).
            context: Optional context dict.

        Yields:
            StreamEvents unmodified (pass-through).
        """
        # Record user input as root cause
        if user_prompt:
            self._record("user_input", {"content": user_prompt, "context": context or {}})

        # Track LLM response state
        pending_tool_calls: list[dict] = []

        async for event in stream:
            # Record provenance for each event type
            if event.type == EventType.text:
                # Text from LLM — could be final response or part of streaming
                tc_data = event.data or {}
                # Check if this is from a tool call context
                self._record("llm_response", {
                    "content": event.content or "",
                    "tool_calls": tc_data.get("tool_calls", []),
                })
                pending_tool_calls = []

            elif event.type == EventType.tool_call:
                tc_name = event.data.get("name", "?")
                tc_args = event.data.get("args", {})
                # Record tool call — caused by the last llm_response
                self._record("tool_call", {
                    "name": tc_name,
                    "args": tc_args,
                    "id": event.data.get("id", ""),
                })
                pending_tool_calls.append({"name": tc_name, "args": tc_args})

            elif event.type == EventType.tool_result:
                tc_name = event.data.get("name", "?")
                tc_content = event.data.get("content", "")
                tc_is_error = event.data.get("is_error", False)
                # Record tool result — caused by the last tool_call
                self._record("tool_result", {
                    "name": tc_name,
                    "content": tc_content,
                    "is_error": tc_is_error,
                })
                # The result will cause the next LLM call — update causer
                # The _record already set self._last_causer to this result

            elif event.type == EventType.state:
                state_data = event.data or {}
                self._record("state_transition", {
                    "from": state_data.get("from_state", ""),
                    "to": state_data.get("state", ""),
                    "iteration": state_data.get("iteration", 0),
                })
                # Update iteration counter
                if "iteration" in state_data:
                    self._iteration = state_data["iteration"]

            elif event.type == EventType.error:
                self._record("error", {
                    "message": event.content or "",
                })

            elif event.type == EventType.status:
                # Don't record status events as provenance nodes
                pass

            # Yield the original event unchanged
            yield event

        # Record the final iteration as done
        self._record("state_transition", {
            "from": "running",
            "to": "completed",
            "iteration": self._iteration,
        })

    # ── Query methods ───────────────────────────────────────────────────

    def trace_decision(self, node_id: str) -> list[ProvenanceNode]:
        """Walk up the causal chain from a node to the root.

        Args:
            node_id: The ID of the node to trace from.

        Returns:
            List of ProvenanceNodes from root to the specified node.
        """
        chain: list[ProvenanceNode] = []
        current_id: str | None = node_id

        while current_id is not None:
            node = self._nodes.get(current_id)
            if node is None:
                # Try to load from store
                if self._store:
                    node = self._store.load_node(self._session_id, current_id)
                if node is None:
                    break
                self._nodes[node.id] = node  # Add to local cache
            chain.insert(0, node)
            current_id = node.caused_by

        return chain

    def critical_path(self, target_node_id: str | None = None) -> list[ProvenanceNode]:
        """Find the minimal set of nodes on the critical path.

        The critical path is the shortest causal chain from root to target
        that includes all decision points (tool calls, errors).

        Args:
            target_node_id: Target node. If None, uses the last recorded node.

        Returns:
            List of ProvenanceNodes on the critical path.
        """
        if target_node_id is None:
            # Use the last node
            if not self._nodes:
                return []
            target_node_id = list(self._nodes.keys())[-1]

        chain = self.trace_decision(target_node_id)

        # Filter to keep only decision nodes (tool calls, errors, user input)
        decision_types = {"user_input", "tool_call", "error", "state_transition"}
        critical = [n for n in chain if n.node_type in decision_types
                    or n == chain[-1]]  # Always include target

        if not critical:
            return chain
        return critical

    def path(self) -> list[ProvenanceNode]:
        """Get the full causal path from root to the last node."""
        if not self._nodes:
            return []
        last_id = list(self._nodes.keys())[-1]
        return self.trace_decision(last_id)

    def graph(self) -> dict[str, Any]:
        """Get the full provenance graph as a serializable dict.

        Returns:
            dict with 'nodes' and 'edges' lists for graph rendering.
        """
        nodes_list = []
        edges_list: list[dict[str, str]] = []

        for node in self._nodes.values():
            nodes_list.append({
                "id": node.id,
                "type": node.node_type,
                "label": node.path_label(),
                "causal_group": node.causal_group,
                "timestamp": node.timestamp,
                "duration_ms": node.duration_ms,
            })
            if node.caused_by:
                edges_list.append({
                    "source": node.caused_by,
                    "target": node.id,
                    "type": "causes",
                })

        return {
            "session_id": self._session_id,
            "nodes": nodes_list,
            "edges": edges_list,
            "node_count": len(nodes_list),
            "edge_count": len(edges_list),
        }

    def by_type(self, node_type: str) -> list[ProvenanceNode]:
        """Get all nodes of a specific type."""
        return [n for n in self._nodes.values() if n.node_type == node_type]

    def tool_calls(self) -> list[ProvenanceNode]:
        """Get all tool call nodes."""
        return self.by_type("tool_call")

    def errors(self) -> list[ProvenanceNode]:
        """Get all error nodes."""
        return self.by_type("error")

    # ── Formatting ──────────────────────────────────────────────────────

    def format_chain(self, chain: list[ProvenanceNode] | None = None) -> str:
        """Format a causal chain as a human-readable string.

        Args:
            chain: Optional chain from trace_decision(). Uses path() if None.

        Returns:
            Indented causal chain: root → ... → target.
        """
        if chain is None:
            chain = self.path()

        lines: list[str] = []
        for i, node in enumerate(chain):
            prefix = "  " * i + "└─ " if i > 0 else "▶ "
            label = node.path_label()
            dur = f" [{node.duration_ms:.0f}ms]" if node.duration_ms else ""
            lines.append(f"{prefix}{node.node_type}: {label}{dur}")

        return "\n".join(lines)

    def summary(self) -> dict[str, Any]:
        """Get summary statistics about the recorded provenance."""
        type_counts: dict[str, int] = {}
        for n in self._nodes.values():
            type_counts[n.node_type] = type_counts.get(n.node_type, 0) + 1
        return {
            "session_id": self._session_id,
            "nodes": len(self._nodes),
            "by_type": type_counts,
            "tool_calls": len(self.by_type("tool_call")),
            "errors": len(self.by_type("error")),
            "duration_seconds": time.time() - self._start_time,
        }


# ── ProvenanceStore — SQLite persistence ──────────────────────────────────


class ProvenanceStore:
    """SQLite-backed persistence for provenance data.

    Stores provenance nodes and supports session-scoped queries.
    Used automatically when ProvenanceTracker is created with a store.

    Usage:
        store = ProvenanceStore("provenance.db")
        tracker = ProvenanceTracker(store=store)
        # ... track agent execution ...
        nodes = store.load_session(session_id)
    """

    def __init__(self, db_path: str | Path = "chainforge_provenance.db"):
        self._db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None
        self._lock = __import__("threading").Lock()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self._db_path))
            self._conn.row_factory = sqlite3.Row
            self._init_db()
        return self._conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS provenance_sessions (
                session_id TEXT PRIMARY KEY,
                created_at REAL NOT NULL,
                node_count INTEGER DEFAULT 0,
                metadata TEXT DEFAULT '{}'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS provenance_nodes (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                node_type TEXT NOT NULL,
                caused_by TEXT,
                causal_group TEXT DEFAULT '0',
                data TEXT NOT NULL,
                timestamp REAL NOT NULL,
                duration_ms REAL,
                FOREIGN KEY (session_id) REFERENCES provenance_sessions(session_id)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_pn_session
            ON provenance_nodes(session_id, timestamp)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_pn_caused_by
            ON provenance_nodes(caused_by)
        """)
        conn.commit()

    def save_node(self, session_id: str, node: ProvenanceNode) -> None:
        """Save a provenance node to the store."""
        with self._lock:
            conn = self._get_conn()
            conn.execute("""
                INSERT OR REPLACE INTO provenance_nodes
                (id, session_id, node_type, caused_by, causal_group, data,
                 timestamp, duration_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                node.id, session_id, node.node_type, node.caused_by,
                node.causal_group,
                json.dumps(node.data, default=str),
                node.timestamp, node.duration_ms,
            ))
            # Upsert session
            conn.execute("""
                INSERT INTO provenance_sessions (session_id, created_at, node_count)
                VALUES (?, ?, 1)
                ON CONFLICT(session_id) DO UPDATE SET
                    node_count = node_count + 1,
                    metadata = metadata
            """, (session_id, time.time()))
            conn.commit()

    def load_node(self, session_id: str, node_id: str) -> ProvenanceNode | None:
        """Load a single provenance node."""
        with self._lock:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT * FROM provenance_nodes WHERE id = ? AND session_id = ?",
                (node_id, session_id),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_node(row)

    def load_session(self, session_id: str) -> list[ProvenanceNode]:
        """Load all provenance nodes for a session."""
        with self._lock:
            conn = self._get_conn()
            rows = conn.execute(
                "SELECT * FROM provenance_nodes WHERE session_id = ? ORDER BY timestamp ASC",
                (session_id,),
            ).fetchall()
        return [self._row_to_node(row) for row in rows]

    def load_session_graph(self, session_id: str) -> dict[str, Any]:
        """Load a session's full provenance graph."""
        nodes = self.load_session(session_id)
        edges = []
        node_list = []
        for n in nodes:
            node_list.append({
                "id": n.id, "type": n.node_type, "label": n.path_label(),
                "causal_group": n.causal_group, "timestamp": n.timestamp,
            })
            if n.caused_by:
                edges.append({"source": n.caused_by, "target": n.id, "type": "causes"})
        return {"session_id": session_id, "nodes": node_list, "edges": edges,
                "node_count": len(node_list), "edge_count": len(edges)}

    def list_sessions(self, limit: int = 20) -> list[dict[str, Any]]:
        """List provenance sessions."""
        with self._lock:
            conn = self._get_conn()
            rows = conn.execute(
                "SELECT * FROM provenance_sessions ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "session_id": r["session_id"],
                "created_at": r["created_at"],
                "node_count": r["node_count"],
            }
            for r in rows
        ]

    def _row_to_node(self, row: sqlite3.Row) -> ProvenanceNode:
        return ProvenanceNode(
            id=row["id"],
            node_type=row["node_type"],
            caused_by=row["caused_by"],
            causal_group=row["causal_group"] or "0",
            data=json.loads(row["data"]) if isinstance(row["data"], str) else {},
            timestamp=row["timestamp"],
            duration_ms=row["duration_ms"],
        )

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
