# Copyright 2026 ChainForge Contributors. Apache 2.0.
"""Priority-ordered handoff queue with SLA tracking."""

from __future__ import annotations

import time
from collections import deque

from chainforge.enterprise.handoff.package import HandoffPackage

_PRIORITY_ORDER: dict[str, int] = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
}


class HandoffQueue:
    """A priority-ordered (critical > high > medium > low, then FIFO) handoff queue.

    Statuses: pending, assigned, resolved.
    """

    def __init__(self) -> None:
        self._buckets: dict[str, deque[HandoffPackage]] = {
            "critical": deque(),
            "high": deque(),
            "medium": deque(),
            "low": deque(),
        }
        self._status: dict[str, str] = {}  # run_id -> status
        self._assignee: dict[str, str] = {}  # run_id -> assignee
        self._resolution: dict[str, str] = {}  # run_id -> resolution text
        self._resolved_at: dict[str, float] = {}  # run_id -> resolved timestamp
        self._created_at: dict[str, float] = {}  # run_id -> creation timestamp

    def enqueue(self, pkg: HandoffPackage) -> str:
        """Add a package to the queue.  Returns the run_id."""
        priority = pkg.priority if pkg.priority in self._buckets else "medium"
        self._buckets[priority].append(pkg)
        self._status[pkg.run_id] = "pending"
        self._created_at[pkg.run_id] = pkg.created_at
        return pkg.run_id

    def next(self) -> HandoffPackage | None:
        """Return the next pending package sorted by priority then FIFO, or None."""
        for level in ("critical", "high", "medium", "low"):
            bucket = self._buckets[level]
            while bucket:
                pkg = bucket.popleft()
                if self._status.get(pkg.run_id) == "pending":
                    return pkg
        return None

    def assign(self, item_id: str, assignee: str) -> bool:
        """Mark an item as assigned to a human.  Returns True on success."""
        if self._status.get(item_id) != "pending":
            return False
        self._status[item_id] = "assigned"
        self._assignee[item_id] = assignee
        return True

    def resolve(self, item_id: str, resolution: str) -> bool:
        """Mark an item as resolved.  Returns True on success."""
        if self._status.get(item_id) != "assigned":
            return False
        self._status[item_id] = "resolved"
        self._resolution[item_id] = resolution
        self._resolved_at[item_id] = time.time()
        return True

    def list(self, status_filter: str | None = None) -> list[dict]:
        """Return all items, optionally filtered by status."""
        items: list[dict] = []
        for level in ("critical", "high", "medium", "low"):
            for pkg in self._buckets[level]:
                st = self._status.get(pkg.run_id, "pending")
                if status_filter and st != status_filter:
                    continue
                items.append(
                    {
                        "run_id": pkg.run_id,
                        "summary": pkg._summary,
                        "priority": pkg.priority,
                        "status": st,
                        "assignee": self._assignee.get(pkg.run_id),
                        "resolution": self._resolution.get(pkg.run_id),
                    }
                )
        return items

    def sla_stats(self) -> dict:
        """Return SLA statistics across all items in the queue."""
        now = time.time()
        resolved_ids = [
            rid for rid, st in self._status.items() if st == "resolved"
        ]
        resolved_today = sum(
            1
            for rid in resolved_ids
            if self._resolved_at.get(rid, 0)
            > now - 86400
        )
        open_items = sum(
            1 for st in self._status.values() if st in ("pending", "assigned")
        )

        response_times: list[float] = []
        breach_count = 0
        for rid in resolved_ids:
            created = self._created_at.get(rid, now)
            resolved = self._resolved_at.get(rid, now)
            response_times.append((resolved - created) / 60.0)

            # Check SLA breach: find the package and compare
            for level in self._buckets:
                for pkg in self._buckets[level]:
                    if pkg.run_id == rid and pkg.sla:
                        hours_elapsed = (resolved - created) / 3600.0
                        if hours_elapsed > pkg.sla.resolution_time_hours:
                            breach_count += 1
                        break

        avg_response_minutes = (
            sum(response_times) / len(response_times) if response_times else 0.0
        )
        sla_breach_rate = (
            breach_count / len(resolved_ids) if resolved_ids else 0.0
        )

        return {
            "avg_response_minutes": round(avg_response_minutes, 1),
            "sla_breach_rate": round(sla_breach_rate, 2),
            "open_items": open_items,
            "resolved_today": resolved_today,
        }
