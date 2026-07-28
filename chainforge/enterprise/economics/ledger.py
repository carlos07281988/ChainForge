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
"""TokenLedger -- persistent storage for cost records."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class CostRecord(BaseModel):
    """A single LLM call cost record."""

    timestamp: float = Field(default_factory=time.time)
    model: str = Field(default="unknown")
    provider: str = Field(default="unknown")
    input_tokens: int = Field(default=0)
    output_tokens: int = Field(default=0)
    cost: float = Field(default=0.0)
    duration_ms: float = Field(default=0.0)
    attribution: dict[str, str] = Field(default_factory=dict)


class TokenLedger:
    """Storage backend for cost records.

    Supports 'memory' (ephemeral) and 'sqlite' (persistent) backends.

    Usage:
        ledger = TokenLedger(backend="sqlite", db_path="costs.db")
        ledger.record(CostRecord(model="gpt-4o", cost=0.05, ...))
        records = ledger.query(group_by="model", period="today")
    """

    def __init__(self, backend: str = "memory", db_path: str | None = None):
        self._backend = backend
        self._memory: list[CostRecord] = []
        self._conn: sqlite3.Connection | None = None
        if backend == "sqlite":
            path = db_path or "chainforge_costs.db"
            self._conn = sqlite3.connect(str(Path(path)), check_same_thread=False)
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS costs ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "timestamp REAL, model TEXT, provider TEXT, "
                "input_tokens INTEGER, output_tokens INTEGER, "
                "cost REAL, duration_ms REAL, "
                "attribution TEXT"
                ")"
            )
            self._conn.commit()

    def record(self, record: CostRecord) -> None:
        """Persist a cost record."""
        if self._backend == "memory":
            self._memory.append(record)
        elif self._conn:
            self._conn.execute(
                "INSERT INTO costs (timestamp, model, provider, "
                "input_tokens, output_tokens, cost, duration_ms, attribution) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record.timestamp,
                    record.model,
                    record.provider,
                    record.input_tokens,
                    record.output_tokens,
                    record.cost,
                    record.duration_ms,
                    json.dumps(record.attribution),
                ),
            )
            self._conn.commit()

    def query(
        self,
        group_by: str = "model",
        period: str | tuple[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        """Query aggregated cost data.

        Args:
            group_by: Dimension to group by -- 'model', 'provider', 'project',
                      'department', 'tenant'.
            period: Time range -- 'today', 'this-month', 'last-30-days',
                    or (start, end) ISO date strings.

        Returns:
            List of aggregated rows.
        """
        if self._backend == "memory":
            return self._query_memory(group_by, period)
        return self._query_sqlite(group_by, period)

    def _query_memory(
        self, group_by: str, period: str | tuple[str, str] | None
    ) -> list[dict[str, Any]]:
        filtered = self._filter_by_period(self._memory, period)
        return self._aggregate(filtered, group_by)

    def _query_sqlite(
        self, group_by: str, period: str | tuple[str, str] | None
    ) -> list[dict[str, Any]]:
        if not self._conn:
            return []
        where, params = self._build_period_where(period)
        # For attribution fields, extract from JSON
        if group_by in ("project", "department", "tenant"):
            col = f"json_extract(attribution, '$.{group_by}')"
        else:
            col = group_by
        sql = (
            f"SELECT {col} as dimension, "
            f"COUNT(*) as calls, "
            f"SUM(input_tokens) as total_input_tokens, "
            f"SUM(output_tokens) as total_output_tokens, "
            f"SUM(cost) as total_cost, "
            f"AVG(duration_ms) as avg_duration_ms "
            f"FROM costs {where} "
            f"GROUP BY {col} "
            f"ORDER BY total_cost DESC"
        )
        rows = self._conn.execute(sql, params).fetchall()
        return [
            {
                "dimension": r[0] or "unknown",
                "calls": r[1],
                "total_input_tokens": r[2],
                "total_output_tokens": r[3],
                "total_cost": round(r[4], 6),
                "avg_duration_ms": round(r[5], 1) if r[5] else 0.0,
            }
            for r in rows
        ]

    @staticmethod
    def _filter_by_period(
        records: list[CostRecord],
        period: str | tuple[str, str] | None,
    ) -> list[CostRecord]:
        if not period or period == "all":
            return records
        now = time.time()
        if period == "today":
            cutoff = now - 86400
            return [r for r in records if r.timestamp >= cutoff]
        if period == "this-month":
            # Approximate: last 30 days
            cutoff = now - 86400 * 30
            return [r for r in records if r.timestamp >= cutoff]
        if period == "last-30-days":
            cutoff = now - 86400 * 30
            return [r for r in records if r.timestamp >= cutoff]
        if isinstance(period, tuple) and len(period) == 2:
            # (start_iso, end_iso)
            start = _iso_to_ts(period[0])
            end = _iso_to_ts(period[1])
            return [r for r in records if start <= r.timestamp <= end]
        return records

    @staticmethod
    def _build_period_where(
        period: str | tuple[str, str] | None,
    ) -> tuple[str, list]:
        if not period or period == "all":
            return "", []
        now = time.time()
        if period == "today":
            cutoff = now - 86400
            return "WHERE timestamp >= ?", [cutoff]
        if period in ("this-month", "last-30-days"):
            cutoff = now - 86400 * 30
            return "WHERE timestamp >= ?", [cutoff]
        if isinstance(period, tuple) and len(period) == 2:
            start = _iso_to_ts(period[0])
            end = _iso_to_ts(period[1])
            return "WHERE timestamp >= ? AND timestamp <= ?", [start, end]
        return "", []

    @staticmethod
    def _aggregate(
        records: list[CostRecord], group_by: str
    ) -> list[dict[str, Any]]:
        groups: dict[str, dict[str, Any]] = {}
        for r in records:
            if group_by == "model":
                key = r.model
            elif group_by == "provider":
                key = r.provider
            elif group_by in ("project", "department", "tenant"):
                key = r.attribution.get(group_by, "unknown")
            else:
                key = getattr(r, group_by, "unknown")

            if key not in groups:
                groups[key] = {
                    "dimension": key,
                    "calls": 0,
                    "total_input_tokens": 0,
                    "total_output_tokens": 0,
                    "total_cost": 0.0,
                }
            g = groups[key]
            g["calls"] += 1
            g["total_input_tokens"] += r.input_tokens
            g["total_output_tokens"] += r.output_tokens
            g["total_cost"] += r.cost

        return sorted(groups.values(), key=lambda x: x["total_cost"], reverse=True)

    def total_cost(self, period: str | tuple[str, str] | None = None) -> float:
        """Get total cost for a period."""
        rows = self.query(group_by="model", period=period)
        return sum(r["total_cost"] for r in rows)

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None


def _iso_to_ts(iso: str) -> float:
    """Convert ISO date string to Unix timestamp."""
    import datetime
    try:
        dt = datetime.datetime.fromisoformat(iso)
        return dt.timestamp()
    except (ValueError, TypeError):
        return 0.0
