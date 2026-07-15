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
"""TraceStore — persist traces to SQLite for querying and dashboard.

Usage:
    from chainforge.tracing.store import TraceStore

    store = TraceStore("traces.db")
    await store.save(trace)
    traces = await store.list_traces(limit=10)
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from chainforge.logging import get_logger
from chainforge.tracing.tracer import Trace, Span

logger = get_logger("tracing.store")


class TraceStore:
    """SQLite-backed trace storage for monitoring and dashboard.

    Persists traces and spans for querying by agent_id, session, time range.
    """

    def __init__(self, db_path: str | Path = "chainforge_traces.db"):
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
            CREATE TABLE IF NOT EXISTS traces (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                start_time REAL NOT NULL,
                end_time REAL,
                duration_ms REAL,
                metadata TEXT DEFAULT '{}',
                span_count INTEGER DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS spans (
                id TEXT PRIMARY KEY,
                trace_id TEXT NOT NULL,
                name TEXT NOT NULL,
                parent_id TEXT,
                start_time REAL NOT NULL,
                end_time REAL,
                duration_ms REAL,
                attributes TEXT DEFAULT '{}',
                FOREIGN KEY (trace_id) REFERENCES traces(id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_spans_trace ON spans(trace_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_traces_time ON traces(start_time)")
        conn.commit()

    async def save(self, trace: Trace) -> None:
        """Persist a trace with all its spans."""
        now = time.time()
        duration = trace.duration_ms

        with self._lock:
            conn = self._get_conn()
            conn.execute(
                "INSERT OR REPLACE INTO traces (id, name, start_time, end_time, duration_ms, metadata, span_count) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    trace.id,
                    trace.name,
                    trace.start_time,
                    trace.end_time or now,
                    duration,
                    json.dumps(trace.metadata, default=str),
                    len(trace.spans),
                ),
            )
            for span in trace.spans:
                conn.execute(
                    "INSERT OR REPLACE INTO spans (id, trace_id, name, parent_id, start_time, end_time, duration_ms, attributes) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        span.id,
                        trace.id,
                        span.name,
                        span.parent_id,
                        span.start_time,
                        span.end_time or now,
                        span.duration_ms,
                        json.dumps(span.attributes, default=str),
                    ),
                )
            conn.commit()

    async def list_traces(
        self,
        limit: int = 20,
        offset: int = 0,
        agent_id: str | None = None,
        time_from: float | None = None,
        time_to: float | None = None,
    ) -> list[dict[str, Any]]:
        """List traces with optional filtering."""
        with self._lock:
            conn = self._get_conn()
            query = "SELECT * FROM traces WHERE 1=1"
            params: list[Any] = []
            if agent_id:
                query += " AND metadata LIKE ?"
                params.append(f"%{agent_id}%")
            if time_from:
                query += " AND start_time >= ?"
                params.append(time_from)
            if time_to:
                query += " AND start_time <= ?"
                params.append(time_to)
            query += " ORDER BY start_time DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            rows = conn.execute(query, params).fetchall()
        return [
            {
                "id": row["id"],
                "name": row["name"],
                "start_time": row["start_time"],
                "end_time": row["end_time"],
                "duration_ms": row["duration_ms"],
                "metadata": json.loads(row["metadata"]) if isinstance(row["metadata"], str) else {},
                "span_count": row["span_count"],
            }
            for row in rows
        ]

    async def get_trace(self, trace_id: str) -> dict[str, Any] | None:
        """Get a trace with all its spans."""
        with self._lock:
            conn = self._get_conn()
            row = conn.execute("SELECT * FROM traces WHERE id = ?", (trace_id,)).fetchone()
            if row is None:
                return None
            span_rows = conn.execute(
                "SELECT * FROM spans WHERE trace_id = ? ORDER BY start_time ASC",
                (trace_id,),
            ).fetchall()
        return {
            "id": row["id"],
            "name": row["name"],
            "start_time": row["start_time"],
            "end_time": row["end_time"],
            "duration_ms": row["duration_ms"],
            "metadata": json.loads(row["metadata"]) if isinstance(row["metadata"], str) else {},
            "span_count": row["span_count"],
            "spans": [
                {
                    "id": s["id"],
                    "name": s["name"],
                    "parent_id": s["parent_id"],
                    "start_time": s["start_time"],
                    "end_time": s["end_time"],
                    "duration_ms": s["duration_ms"],
                    "attributes": json.loads(s["attributes"]) if isinstance(s["attributes"], str) else {},
                }
                for s in span_rows
            ],
        }

    async def get_stats(self) -> dict[str, Any]:
        """Get aggregate statistics."""
        with self._lock:
            conn = self._get_conn()
            total = conn.execute("SELECT COUNT(*) AS c FROM traces").fetchone()
            avg_duration = conn.execute("SELECT AVG(duration_ms) AS avg FROM traces WHERE duration_ms IS NOT NULL").fetchone()
            total_spans = conn.execute("SELECT SUM(span_count) AS s FROM traces").fetchone()
        return {
            "total_traces": total["c"] if total else 0,
            "avg_duration_ms": round(avg_duration["avg"], 2) if avg_duration and avg_duration["avg"] else 0,
            "total_spans": total_spans["s"] or 0,
        }

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
