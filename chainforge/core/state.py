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
"""Agent state machine — explicit, observable state transitions.

States represent distinct phases of agent execution:
  initializing -> thinking -> [executing_tool -> observing -> thinking] -> responding -> done

Also provides Checkpointer protocol for state persistence.
"""

from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Callable
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field
from typing_extensions import Protocol, runtime_checkable

from chainforge.logging import get_logger

logger = get_logger("state")


class AgentState(str, Enum):
    """All possible states of an agent execution."""

    initializing = "initializing"
    thinking = "thinking"
    executing_tool = "executing_tool"
    observing = "observing"
    responding = "responding"
    error = "error"
    done = "done"


class StateTransition(BaseModel):
    """A single state transition with metadata."""

    from_state: AgentState | None = Field(default=None, description="Previous state")
    to_state: AgentState = Field(description="New state")
    iteration: int = Field(default=0, description="Current iteration")
    depth: int = Field(default=0, description="Nesting depth (for multi-agent)")
    tool_name: str | None = Field(default=None, description="Tool being executed, if applicable")
    message: str | None = Field(default=None, description="Human-readable status")
    timestamp: float = Field(default_factory=time.time)


class ThreadInfo(BaseModel):
    """Metadata for a checkpoint thread/session."""
    thread_id: str = Field(description="Thread identifier")
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)
    checkpoint_count: int = Field(default=0)


# ── Checkpointer Protocol ────────────────────────────────────────────────


@runtime_checkable
class Checkpointer(Protocol):
    """Protocol for agent state checkpointing.

    Implementations save/load the full agent state (messages, context, execution
    state) across sessions, enabling pause/resume and thread-based isolation.
    """

    async def save(
        self,
        state: dict[str, Any],
        thread_id: str,
        checkpoint_id: str | None = None,
    ) -> str:
        """Save a checkpoint and return its ID."""
        ...

    async def load(
        self,
        thread_id: str,
        checkpoint_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Load the latest (or specific) checkpoint for a thread."""
        ...

    async def list_threads(self) -> list[ThreadInfo]:
        """List all threads with metadata."""
        ...

    async def list_checkpoints(self, thread_id: str) -> list[str]:
        """List checkpoint IDs for a thread."""
        ...

    async def delete_thread(self, thread_id: str) -> None:
        """Delete all checkpoints for a thread."""
        ...


# ── InMemoryCheckpointer ─────────────────────────────────────────────────


class InMemoryCheckpointer:
    """In-memory implementation of the Checkpointer protocol.

    Stores checkpoints in a dict. Useful for testing and single-process use.
    Not persistent across process restarts.
    """

    def __init__(self):
        self._checkpoints: dict[str, dict[str, dict[str, Any]]] = {}  # thread_id -> {checkpoint_id -> state}
        self._thread_meta: dict[str, ThreadInfo] = {}

    async def save(
        self,
        state: dict[str, Any],
        thread_id: str,
        checkpoint_id: str | None = None,
    ) -> str:
        if checkpoint_id is None:
            checkpoint_id = f"ckp_{int(time.time() * 1000)}_{id(state)}"
        if thread_id not in self._checkpoints:
            self._checkpoints[thread_id] = {}
            self._thread_meta[thread_id] = ThreadInfo(
                thread_id=thread_id,
                created_at=time.time(),
            )
        # Deep copy to avoid mutation
        import copy
        self._checkpoints[thread_id][checkpoint_id] = copy.deepcopy(state)
        meta = self._thread_meta[thread_id]
        meta.updated_at = time.time()
        meta.checkpoint_count = len(self._checkpoints[thread_id])
        return checkpoint_id

    async def load(
        self,
        thread_id: str,
        checkpoint_id: str | None = None,
    ) -> dict[str, Any] | None:
        thread = self._checkpoints.get(thread_id)
        if thread is None:
            return None
        if checkpoint_id is not None:
            state = thread.get(checkpoint_id)
            if state is not None:
                import copy
                return copy.deepcopy(state)
            return None
        # Return the latest checkpoint
        if not thread:
            return None
        latest_id = max(thread.keys(), key=lambda k: self._parse_ckp_timestamp(k))
        import copy
        return copy.deepcopy(thread[latest_id])

    async def list_threads(self) -> list[ThreadInfo]:
        return list(self._thread_meta.values())

    async def list_checkpoints(self, thread_id: str) -> list[str]:
        thread = self._checkpoints.get(thread_id, {})
        return sorted(thread.keys(), key=lambda k: self._parse_ckp_timestamp(k))

    async def delete_thread(self, thread_id: str) -> None:
        self._checkpoints.pop(thread_id, None)
        self._thread_meta.pop(thread_id, None)

    @staticmethod
    def _parse_ckp_timestamp(key: str) -> float:
        try:
            return float(key.split("_")[1]) if "_" in key else 0.0
        except (ValueError, IndexError):
            return 0.0


# ── SQLiteCheckpointer ────────────────────────────────────────────────────


class SQLiteCheckpointer:
    """SQLite-backed implementation of the Checkpointer protocol.

    Persists checkpoints to a SQLite database file. Supports concurrent
    threads and process restarts.

    Usage:
        checkpointer = SQLiteCheckpointer("agent_state.db")
        await checkpointer.save(state, thread_id="session-1")
        loaded = await checkpointer.load(thread_id="session-1")
    """

    def __init__(self, db_path: str | Path = "chainforge_state.db"):
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
            CREATE TABLE IF NOT EXISTS threads (
                thread_id TEXT PRIMARY KEY,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                metadata TEXT DEFAULT '{}'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS checkpoints (
                checkpoint_id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL,
                state TEXT NOT NULL,
                created_at REAL NOT NULL,
                FOREIGN KEY (thread_id) REFERENCES threads(thread_id)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_checkpoints_thread
            ON checkpoints(thread_id, created_at)
        """)
        conn.commit()

    async def save(
        self,
        state: dict[str, Any],
        thread_id: str,
        checkpoint_id: str | None = None,
    ) -> str:
        if checkpoint_id is None:
            checkpoint_id = f"ckp_{int(time.time() * 1000)}_{hash(str(state)) % (10 ** 8)}"
        now = time.time()
        state_json = json.dumps(state, default=str, ensure_ascii=False)
        meta_json = json.dumps(state.get("_metadata", {}), default=str, ensure_ascii=False)

        with self._lock:
            conn = self._get_conn()
            conn.execute("""
                INSERT OR REPLACE INTO threads (thread_id, created_at, updated_at, metadata)
                VALUES (?, COALESCE((SELECT created_at FROM threads WHERE thread_id = ?), ?), ?, ?)
            """, (thread_id, thread_id, now, now, meta_json))
            conn.execute("""
                INSERT OR REPLACE INTO checkpoints (checkpoint_id, thread_id, state, created_at)
                VALUES (?, ?, ?, ?)
            """, (checkpoint_id, thread_id, state_json, now))
            conn.commit()
        return checkpoint_id

    async def load(
        self,
        thread_id: str,
        checkpoint_id: str | None = None,
    ) -> dict[str, Any] | None:
        with self._lock:
            conn = self._get_conn()
            if checkpoint_id is not None:
                row = conn.execute(
                    "SELECT state FROM checkpoints WHERE checkpoint_id = ? AND thread_id = ?",
                    (checkpoint_id, thread_id),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT state FROM checkpoints WHERE thread_id = ? ORDER BY created_at DESC LIMIT 1",
                    (thread_id,),
                ).fetchone()
        if row is None:
            return None
        return json.loads(row["state"])

    async def list_threads(self) -> list[ThreadInfo]:
        with self._lock:
            conn = self._get_conn()
            rows = conn.execute(
                "SELECT thread_id, created_at, updated_at, metadata, "
                "(SELECT COUNT(*) FROM checkpoints WHERE thread_id = t.thread_id) AS ckp_count "
                "FROM threads t ORDER BY updated_at DESC"
            ).fetchall()
        return [
            ThreadInfo(
                thread_id=row["thread_id"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                metadata=json.loads(row["metadata"]) if isinstance(row["metadata"], str) else {},
                checkpoint_count=row["ckp_count"],
            )
            for row in rows
        ]

    async def list_checkpoints(self, thread_id: str) -> list[str]:
        with self._lock:
            conn = self._get_conn()
            rows = conn.execute(
                "SELECT checkpoint_id FROM checkpoints WHERE thread_id = ? ORDER BY created_at ASC",
                (thread_id,),
            ).fetchall()
        return [row["checkpoint_id"] for row in rows]

    async def delete_thread(self, thread_id: str) -> None:
        with self._lock:
            conn = self._get_conn()
            conn.execute("DELETE FROM checkpoints WHERE thread_id = ?", (thread_id,))
            conn.execute("DELETE FROM threads WHERE thread_id = ?", (thread_id,))
            conn.commit()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None


# ── StateTracker (unchanged, with checkpoint integration) ────────────────


class StateTracker:
    """Tracks agent state transitions and provides observable callbacks.

    Consumers can subscribe to state changes and react accordingly.
    Supports optional checkpointing for pause/resume.
    """

    def __init__(self, checkpointer: Checkpointer | None = None):
        self._current_state: AgentState = AgentState.initializing
        self._iteration: int = 0
        self._depth: int = 0
        self._history: list[StateTransition] = []
        self._listeners: list[Callable[[StateTransition], None]] = []
        self._checkpointer = checkpointer
        self._thread_id: str | None = None
        self._state_snapshot: dict[str, Any] = {}

    @property
    def current_state(self) -> AgentState:
        return self._current_state

    @property
    def iteration(self) -> int:
        return self._iteration

    @property
    def depth(self) -> int:
        return self._depth

    @property
    def history(self) -> list[StateTransition]:
        return list(self._history)

    def bind_checkpointer(self, checkpointer: Checkpointer, thread_id: str) -> None:
        """Bind a checkpointer and thread ID for automatic checkpointing."""
        self._checkpointer = checkpointer
        self._thread_id = thread_id

    def update_snapshot(self, state: dict[str, Any]) -> None:
        """Update the saved state snapshot for checkpointing."""
        self._state_snapshot.update(state)

    async def checkpoint(self) -> str | None:
        """Save a checkpoint of the current state. Returns checkpoint ID or None."""
        if self._checkpointer is None or self._thread_id is None:
            return None
        snapshot = {
            "current_state": self._current_state.value,
            "iteration": self._iteration,
            "depth": self._depth,
            "state": self._state_snapshot,
            "history": [
                {
                    "from": t.from_state.value if t.from_state else None,
                    "to": t.to_state.value,
                    "iteration": t.iteration,
                    "message": t.message,
                }
                for t in self._history
            ],
        }
        return await self._checkpointer.save(snapshot, self._thread_id)

    def on_transition(self, listener: Callable[[StateTransition], None]) -> Callable:
        """Register a listener for state transitions. Returns an unregister function."""
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    def transition(
        self,
        to_state: AgentState,
        *,
        tool_name: str | None = None,
        message: str | None = None,
        iteration: int | None = None,
        depth: int | None = None,
    ) -> StateTransition:
        """Transition to a new state and notify listeners.

        Args:
            to_state: Target state.
            tool_name: Optional tool name (for executing_tool state).
            message: Optional human-readable status message.
            iteration: Current loop iteration. If provided, updates internal counter.
            depth: Nesting depth for multi-agent scenarios.
        """
        old_state = self._current_state

        # Update internal counters when explicitly provided
        if iteration is not None:
            self._iteration = iteration
        if depth is not None:
            self._depth = depth

        t = StateTransition(
            from_state=old_state,
            to_state=to_state,
            iteration=self._iteration,
            depth=self._depth,
            tool_name=tool_name,
            message=message,
        )

        self._history.append(t)
        self._current_state = to_state

        for listener in self._listeners:
            listener(t)

        return t

    def reset(self) -> None:
        """Reset the tracker to initial state."""
        self._current_state = AgentState.initializing
        self._iteration = 0
        self._depth = 0
        self._history.clear()

    def to_stream_events(self):
        """Convert tracked history to StreamEvents for middleware consumption."""
        from chainforge.core.stream import EventType, StreamEvent

        events = []
        for t in self._history:
            data: dict[str, Any] = {
                "state": t.to_state.value,
                "from_state": t.from_state.value if t.from_state else None,
                "iteration": t.iteration,
                "depth": t.depth,
            }
            if t.tool_name:
                data["tool_name"] = t.tool_name
            events.append(
                StreamEvent(
                    type=EventType.state,
                    content=t.message or t.to_state.value,
                    data=data,
                )
            )
        return events
